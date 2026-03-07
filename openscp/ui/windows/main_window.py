"""Main application window — OpenSCP dual-pane SFTP client."""
from __future__ import annotations

import os
import tempfile
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QProgressBar, QMessageBox, QStatusBar,
    QTabWidget,
)

from openscp.utils import i18n
from openscp.utils.i18n import tr
from openscp.utils import theme_manager
from openscp.ui.panels.local_panel import LocalPanel
from openscp.ui.panels.remote_panel import RemotePanel
from openscp.ui.dialogs.connection_manager import ConnectionManagerDialog
from openscp.ui.widgets.text_editor import TextEditorWidget
from openscp.ui.widgets.ssh_terminal import SSHTerminalWidget
from openscp.ui.dialogs.settings_dialog import SettingsDialog
from openscp.ui.widgets.tasks_panel import TasksPanelWidget
from openscp.core.sftp_worker import (
    SFTPConnectWorker, SFTPListWorker, SFTPTransferWorker,
    SFTPDeleteWorker, SFTPMkdirWorker, SFTPFileLoadWorker, SFTPFileSaveWorker,
)

BTN_STYLE = """
    QPushButton {
        background: %(bg)s;
        color: white; border: none; border-radius: 4px;
        padding: 7px 18px; font-weight: 600; font-size: 12px;
    }
    QPushButton:hover { background: %(hover)s; }
    QPushButton:disabled { background: #37474f; color: #607d8b; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Init i18n and theme
        i18n.init()
        self._apply_theme()

        self.setWindowTitle(tr("app.title"))
        self.setMinimumSize(1100, 700)
        self.resize(1300, 820)

        # State
        self.ssh_client = None
        self.sftp_client = None
        self._workers = []
        self._connected_host = ""
        self._current_conn = {}

        self._build_ui()
        self._connect_signals()
        self._set_disconnected_state()

        # Register for i18n changes
        i18n.on_language_changed(self._retranslate)

    def _apply_theme(self):
        name = theme_manager.get_current_theme_name()
        theme = theme_manager.load_theme(name)
        qss = theme_manager.theme_to_qss(theme)
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(qss)

    # ────────────────────────────────────────────────────────────
    #  Build UI
    # ────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_saved = QPushButton(tr("toolbar.connections"))
        self.btn_saved.setObjectName("btn_connections")
        toolbar.addWidget(self.btn_saved)

        self.btn_disconnect = QPushButton(tr("toolbar.disconnect"))
        self.btn_disconnect.setObjectName("btn_disconnect")
        toolbar.addWidget(self.btn_disconnect)

        self.btn_settings = QPushButton(tr("toolbar.settings"))
        self.btn_settings.setObjectName("btn_settings")
        toolbar.addWidget(self.btn_settings)

        self.conn_info_label = QLabel("")
        toolbar.addWidget(self.conn_info_label)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # ── Main splitter (vertical: panels on top, editor/terminal on bottom) ──
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: dual panels
        self.panels_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.panels_splitter.setHandleWidth(3)

        self.local_panel = LocalPanel()
        self.remote_panel = RemotePanel()

        self.panels_splitter.addWidget(self.local_panel)
        self.panels_splitter.addWidget(self.remote_panel)
        self.panels_splitter.setSizes([600, 600])
        self.main_splitter.addWidget(self.panels_splitter)

        # Bottom: tabbed editor + terminal
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setTabsClosable(False)

        self.text_editor = TextEditorWidget()
        self.ssh_terminal = SSHTerminalWidget()
        self.tasks_panel = TasksPanelWidget()

        self.bottom_tabs.addTab(self.ssh_terminal, "🖥 " + tr("terminal.title"))
        self.bottom_tabs.addTab(self.tasks_panel, "🔄 Background Tasks")

        self.main_splitter.addWidget(self.bottom_tabs)
        self.main_splitter.setSizes([500, 250])

        root.addWidget(self.main_splitter, stretch=1)

        # ── Status bar ──
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel(tr("status.disconnected"))
        self.status_label.setStyleSheet("font-weight: 600;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(260)
        self.progress_bar.setVisible(False)

        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.progress_bar)

    # ────────────────────────────────────────────────────────────
    #  Signals
    # ────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.btn_saved.clicked.connect(self._open_connection_manager)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.btn_settings.clicked.connect(self._open_settings)

        self.remote_panel.navigate_requested.connect(self._list_remote_dir)
        self.remote_panel.download_requested.connect(self._download_files)
        self.remote_panel.upload_requested.connect(self._upload_files)
        self.remote_panel.delete_requested.connect(self._delete_remote)
        self.remote_panel.mkdir_requested.connect(self._mkdir_remote)
        self.remote_panel.edit_requested.connect(self._edit_remote_file)

        self.local_panel.upload_requested.connect(lambda paths: self._upload_files(paths, ""))
        self.local_panel.download_requested.connect(self._download_files)

        self.text_editor.save_requested.connect(self._save_editor_file)

    def _retranslate(self):
        """Called when language changes to update UI text."""
        self.setWindowTitle(tr("app.title"))
        self.btn_saved.setText(tr("toolbar.connections"))
        self.btn_disconnect.setText(tr("toolbar.disconnect"))
        self.btn_settings.setText(tr("toolbar.settings"))
        self.bottom_tabs.setTabText(0, "🖥 " + tr("terminal.title"))
        if self.sftp_client:
            self.status_label.setText(tr("status.connected", name=self._connected_host))
        else:
            self.status_label.setText(tr("status.disconnected"))

    # ────────────────────────────────────────────────────────────
    #  Connection Manager
    # ────────────────────────────────────────────────────────────
    def _open_connection_manager(self):
        dlg = ConnectionManagerDialog.open_manager(self)
        if dlg is None:
            return
        dlg.connect_requested.connect(self._on_saved_connect)
        dlg.exec()

    def _on_saved_connect(self, conn: dict):
        host = conn.get("host", "")
        port = conn.get("port", 22)
        user = conn.get("username", "")
        password = conn.get("password", "")
        name = conn.get("name", host)
        private_key = conn.get("private_key", "")
        key_passphrase = conn.get("key_passphrase", "")

        if not host or not user:
            QMessageBox.warning(self, tr("error"), tr("dlg.missing_fields"))
            return

        self._connected_host = name
        self._current_conn = conn
        self.conn_info_label.setText(f"⚡ {name}  ({user}@{host}:{port})")
        self.btn_saved.setEnabled(False)
        self.status_label.setText(tr("status.connecting"))

        worker = SFTPConnectWorker(host, port, user, password, private_key, key_passphrase)
        self.tasks_panel.add_task(worker, f"Connect: {name}")
        worker.connected.connect(lambda: self.tasks_panel.complete_task(worker, "Connected"))
        worker.error.connect(lambda msg: self.tasks_panel.error_task(worker, msg))
        worker.connected.connect(self._on_connected)
        worker.error.connect(self._on_connect_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    # ────────────────────────────────────────────────────────────
    #  Settings
    # ────────────────────────────────────────────────────────────
    def _open_settings(self):
        dlg = SettingsDialog(parent=self)
        dlg.exec()

    # ────────────────────────────────────────────────────────────
    #  Connection
    # ────────────────────────────────────────────────────────────
    def _on_connected(self, ssh, sftp):
        self.ssh_client = ssh
        self.sftp_client = sftp
        self._set_connected_state()

        # Connect terminal
        self.ssh_terminal.connect_to_ssh(ssh)

        try:
            home = sftp.normalize(".")
        except Exception:
            home = "/"
        self._list_remote_dir(home)

    def _on_connect_error(self, msg: str):
        self.btn_saved.setEnabled(True)
        self.conn_info_label.setText("")
        self.status_label.setText(tr("status.connection_failed"))
        QMessageBox.critical(self, tr("error"), msg)

    def _on_disconnect(self):
        self.ssh_terminal.disconnect()
        try:
            if self.sftp_client:
                self.sftp_client.close()
            if self.ssh_client:
                self.ssh_client.close()
        except Exception:
            pass
        self.sftp_client = None
        self.ssh_client = None
        self._connected_host = ""
        self._current_conn = {}
        self.remote_panel.clear()
        self._set_disconnected_state()

    def _set_connected_state(self):
        self.btn_saved.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.status_label.setText(tr("status.connected", name=self._connected_host))

    def _set_disconnected_state(self):
        self.btn_saved.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.conn_info_label.setText("")
        self.status_label.setText(tr("status.disconnected"))

    # ────────────────────────────────────────────────────────────
    #  Remote listing
    # ────────────────────────────────────────────────────────────
    def _list_remote_dir(self, path: str):
        if not self.sftp_client:
            return
        worker = SFTPListWorker(self.sftp_client, path)
        self.tasks_panel.add_task(worker, f"List: {path}")
        worker.finished.connect(lambda path, items: self.tasks_panel.complete_task(worker, "Listed"))
        worker.error.connect(lambda msg: self.tasks_panel.error_task(worker, msg))
        worker.finished.connect(self._on_listing_received)
        worker.error.connect(lambda msg: QMessageBox.warning(self, "Listing Error", msg))
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _on_listing_received(self, path: str, items: list):
        self.remote_panel.populate(path, items)

    # ────────────────────────────────────────────────────────────
    #  Transfers
    # ────────────────────────────────────────────────────────────
    def _upload_files(self, local_paths: list[str], target_dir: str = ""):
        if not self.sftp_client:
            return
        dest_dir = target_dir if target_dir else self.remote_panel.current_path
        for local_path in local_paths:
            if not os.path.isfile(local_path):
                continue
            basename = os.path.basename(local_path)
            remote_dest = dest_dir.rstrip("/") + "/" + basename
            self._start_transfer(SFTPTransferWorker.UPLOAD, local_path, remote_dest)

    def _download_files(self, remote_paths: list[str]):
        if not self.sftp_client:
            return
        local_dir = self.local_panel.current_path
        for remote_path in remote_paths:
            basename = os.path.basename(remote_path)
            local_dest = os.path.join(local_dir, basename)
            self._start_transfer(SFTPTransferWorker.DOWNLOAD, local_dest, remote_path)

    def _start_transfer(self, direction: str, local_path: str, remote_path: str):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        arrow = '↑' if direction == 'upload' else '↓'
        self.progress_bar.setFormat(f"{arrow} {os.path.basename(local_path)}  %p%")

        worker = SFTPTransferWorker(self.sftp_client, direction, local_path, remote_path)
        self.tasks_panel.add_task(worker, f"{direction.capitalize()}: {os.path.basename(local_path)}")
        worker.progress.connect(lambda cur, tot: self.tasks_panel.update_task_progress(worker, cur, tot))
        worker.finished.connect(lambda msg: self.tasks_panel.complete_task(worker, msg))
        worker.error.connect(lambda msg: self.tasks_panel.error_task(worker, msg))
        
        worker.progress.connect(self._on_transfer_progress)
        worker.finished.connect(self._on_transfer_finished)
        worker.error.connect(self._on_transfer_error)
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _on_transfer_progress(self, transferred: int, total: int):
        if total > 0:
            self.progress_bar.setValue(int(transferred * 100 / total))

    def _on_transfer_finished(self, msg: str):
        self.progress_bar.setValue(100)
        self.status_label.setText(f"  ✓ {msg}")
        self._list_remote_dir(self.remote_panel.current_path)
        QTimer.singleShot(2500, self._hide_progress)

    def _on_transfer_error(self, msg: str):
        self.progress_bar.setVisible(False)
        QMessageBox.warning(self, "Transfer Error", msg)

    def _hide_progress(self):
        self.progress_bar.setVisible(False)
        if self.sftp_client:
            self.status_label.setText(tr("status.connected", name=self._connected_host))

    # ────────────────────────────────────────────────────────────
    #  Delete / Mkdir
    # ────────────────────────────────────────────────────────────
    def _delete_remote(self, path: str, is_dir: bool):
        if not self.sftp_client:
            return
        worker = SFTPDeleteWorker(self.sftp_client, path, is_dir)
        self.tasks_panel.add_task(worker, f"Delete: {path}")
        worker.finished.connect(lambda msg: self.tasks_panel.complete_task(worker, msg))
        worker.error.connect(lambda msg: self.tasks_panel.error_task(worker, msg))

        worker.finished.connect(lambda msg: (
            self.status_label.setText(f"  ✓ {msg}"),
            self._list_remote_dir(self.remote_panel.current_path),
        ))
        worker.error.connect(lambda msg: QMessageBox.warning(self, "Delete Error", msg))
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _mkdir_remote(self, path: str):
        if not self.sftp_client:
            return
        worker = SFTPMkdirWorker(self.sftp_client, path)
        self.tasks_panel.add_task(worker, f"Mkdir: {path}")
        worker.finished.connect(lambda msg: self.tasks_panel.complete_task(worker, msg))
        worker.error.connect(lambda msg: self.tasks_panel.error_task(worker, msg))

        worker.finished.connect(lambda msg: (
            self.status_label.setText(f"  ✓ {msg}"),
            self._list_remote_dir(self.remote_panel.current_path),
        ))
        worker.error.connect(lambda msg: QMessageBox.warning(self, "Mkdir Error", msg))
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    # ────────────────────────────────────────────────────────────
    #  Text editor
    # ────────────────────────────────────────────────────────────
    def _edit_remote_file(self, remote_path: str):
        """Download a remote file to temp, open in editor."""
        if not self.sftp_client:
            return
        try:
            attr = self.sftp_client.stat(remote_path)
            if attr.st_size > 5 * 1024 * 1024:
                msg = f"The file '{os.path.basename(remote_path)}' is {attr.st_size / (1024*1024):.1f}MB, which exceeds the recommended 5MB limit. Opening it might freeze the application.\\n\\nAre you sure you want to proceed?"
                reply = QMessageBox.question(self, "Warning: Large File", msg,
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return

            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix="_" + os.path.basename(remote_path))
            tmp_path = tmp.name
            tmp.close()

            worker = SFTPFileLoadWorker(self.sftp_client, remote_path, tmp_path)
            self.tasks_panel.add_task(worker, f"Load Editor: {os.path.basename(remote_path)}")
            worker.progress.connect(lambda cur, tot: self.tasks_panel.update_task_progress(worker, cur, tot))
            worker.error.connect(lambda msg: self.tasks_panel.error_task(worker, msg))
            
            def on_load_success(rpath, content, tpath):
                self.tasks_panel.complete_task(worker, "Loaded")
                self.text_editor.open_file(rpath, content, tpath)
                self.text_editor.show()
                self.text_editor.activateWindow()
            
            worker.finished.connect(on_load_success)
            worker.error.connect(lambda msg: QMessageBox.warning(self, "Editor Download Error", msg))
            worker.finished.connect(lambda *_: self._cleanup_worker(worker))
            
            self._workers.append(worker)
            worker.start()
            
        except Exception as e:
            QMessageBox.warning(self, tr("error"), str(e))

    def _save_editor_file(self, remote_path: str, content: str, local_tmp: str):
        """Save editor content back to the remote server using background thread."""
        if not self.sftp_client:
            QMessageBox.warning(self, tr("error"), tr("terminal.not_connected"))
            return
            
        worker = SFTPFileSaveWorker(self.sftp_client, remote_path, local_tmp, content)
        self.tasks_panel.add_task(worker, f"Save Editor: {os.path.basename(remote_path)}")
        worker.progress.connect(lambda cur, tot: self.tasks_panel.update_task_progress(worker, cur, tot))
        worker.error.connect(lambda msg: self.tasks_panel.error_task(worker, msg))

        def on_save_success(msg):
            self.tasks_panel.complete_task(worker, msg)
            self.status_label.setText(tr("editor.saved", name=os.path.basename(remote_path)))

        worker.finished.connect(on_save_success)
        worker.error.connect(lambda msg: QMessageBox.warning(self, "Editor Save Error", msg))
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        
        self._workers.append(worker)
        worker.start()

    # ────────────────────────────────────────────────────────────
    #  Helpers
    # ────────────────────────────────────────────────────────────
    def _cleanup_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def closeEvent(self, event):
        self._on_disconnect()
        super().closeEvent(event)
