"""SFTP connection and transfer workers running on background threads."""
from __future__ import annotations

import os
import stat as stat_module
import paramiko
from PyQt6.QtCore import QThread, pyqtSignal


class SFTPConnectWorker(QThread):
    """Connects to an SFTP server in the background."""

    connected = pyqtSignal(object, object)  # (ssh_client, sftp_client)
    error = pyqtSignal(str)

    def __init__(self, host: str, port: int, username: str, password: str,
                 private_key: str = "", key_passphrase: str = ""):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key      # base64-encoded key content
        self.key_passphrase = key_passphrase

    def _load_pkey(self) -> paramiko.PKey | None:
        """Try to load a private key from base64-encoded content."""
        if not self.private_key:
            return None
        import base64
        import io
        key_data = base64.b64decode(self.private_key).decode("utf-8")
        key_file = io.StringIO(key_data)
        passphrase = self.key_passphrase or None
        # Try common key types
        for key_class in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
            try:
                key_file.seek(0)
                return key_class.from_private_key(key_file, password=passphrase)
            except Exception:
                continue
        return None

    def run(self):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            pkey = self._load_pkey()
            connect_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": 10,
            }
            if pkey:
                connect_kwargs["pkey"] = pkey
                # Also pass password if provided (some setups need both)
                if self.password:
                    connect_kwargs["password"] = self.password
            else:
                connect_kwargs["password"] = self.password

            ssh.connect(**connect_kwargs)
            sftp = ssh.open_sftp()
            self.connected.emit(ssh, sftp)
        except Exception as exc:
            self.error.emit(str(exc))


class SFTPListWorker(QThread):
    """Lists a remote directory in the background."""

    finished = pyqtSignal(str, list)  # (path, list[SFTPAttributes])
    error = pyqtSignal(str)

    def __init__(self, sftp, remote_path: str):
        super().__init__()
        self.sftp = sftp
        self.remote_path = remote_path

    def run(self):
        try:
            items = self.sftp.listdir_attr(self.remote_path)
            self.finished.emit(self.remote_path, items)
        except Exception as exc:
            self.error.emit(str(exc))


class SFTPTransferWorker(QThread):
    """Handles a single file upload or download with progress reporting."""

    progress = pyqtSignal(int, int)  # (transferred, total)
    finished = pyqtSignal(str)       # operation description
    error = pyqtSignal(str)

    UPLOAD = "upload"
    DOWNLOAD = "download"

    def __init__(self, sftp, direction: str, local_path: str, remote_path: str):
        super().__init__()
        self.sftp = sftp
        self.direction = direction
        self.local_path = local_path
        self.remote_path = remote_path

    def _callback(self, transferred: int, total: int):
        self.progress.emit(transferred, total)

    def run(self):
        try:
            if self.direction == self.UPLOAD:
                self.sftp.put(self.local_path, self.remote_path, callback=self._callback)
                self.finished.emit(f"Uploaded {os.path.basename(self.local_path)}")
            else:
                self.sftp.get(self.remote_path, self.local_path, callback=self._callback)
                self.finished.emit(f"Downloaded {os.path.basename(self.remote_path)}")
        except Exception as exc:
            self.error.emit(str(exc))


class SFTPDeleteWorker(QThread):
    """Deletes a remote file or empty directory."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, sftp, remote_path: str, is_dir: bool = False):
        super().__init__()
        self.sftp = sftp
        self.remote_path = remote_path
        self.is_dir = is_dir

    def _rm_recursive(self, path: str):
        """Recursively delete a remote directory tree."""
        for attr in self.sftp.listdir_attr(path):
            child = path.rstrip("/") + "/" + attr.filename
            if stat_module.S_ISDIR(attr.st_mode):
                self._rm_recursive(child)
            else:
                self.sftp.remove(child)
        self.sftp.rmdir(path)

    def run(self):
        try:
            if self.is_dir:
                self._rm_recursive(self.remote_path)
            else:
                self.sftp.remove(self.remote_path)
            self.finished.emit(f"Deleted {self.remote_path}")
        except Exception as exc:
            self.error.emit(str(exc))


class SFTPMkdirWorker(QThread):
    """Creates a directory on the remote server."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, sftp, remote_path: str):
        super().__init__()
        self.sftp = sftp
        self.remote_path = remote_path

    def run(self):
        try:
            self.sftp.mkdir(self.remote_path)
            self.finished.emit(f"Created {self.remote_path}")
        except Exception as exc:
            self.error.emit(str(exc))


class SFTPFileLoadWorker(QThread):
    """Downloads a file to memory/temp for editing in background."""

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str, str, str)  # (remote_path, content, tmp_path)
    error = pyqtSignal(str)

    def __init__(self, sftp, remote_path: str, tmp_path: str):
        super().__init__()
        self.sftp = sftp
        self.remote_path = remote_path
        self.tmp_path = tmp_path

    def _callback(self, transferred: int, total: int):
        self.progress.emit(transferred, total)

    def run(self):
        try:
            self.sftp.get(self.remote_path, self.tmp_path, callback=self._callback)
            with open(self.tmp_path, "r", errors="replace") as f:
                content = f.read()
            self.finished.emit(self.remote_path, content, self.tmp_path)
        except Exception as exc:
            self.error.emit(str(exc))


class SFTPFileSaveWorker(QThread):
    """Uploads an edited file from memory/temp in background."""

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, sftp, remote_path: str, local_tmp: str, content: str):
        super().__init__()
        self.sftp = sftp
        self.remote_path = remote_path
        self.local_tmp = local_tmp
        self.content = content

    def _callback(self, transferred: int, total: int):
        self.progress.emit(transferred, total)

    def run(self):
        try:
            with open(self.local_tmp, "w") as f:
                f.write(self.content)
            self.sftp.put(self.local_tmp, self.remote_path, callback=self._callback)
            self.finished.emit(f"Saved {os.path.basename(self.remote_path)}")
        except Exception as exc:
            self.error.emit(str(exc))
