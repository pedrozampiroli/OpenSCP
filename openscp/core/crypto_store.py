"""Encrypted connection store — AES-256-GCM with PBKDF2-derived key."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

STORE_DIR = Path.home() / ".openscp"
STORE_FILE = STORE_DIR / "connections.enc"
PBKDF2_ITERATIONS = 600_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from a password + salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _encrypt(data: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt data with AES-256-GCM. Returns (nonce, ciphertext)."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data, None)
    return nonce, ct


def _decrypt(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM data. Raises InvalidTag on wrong key."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


class CryptoStore:
    """Manages encrypted connection storage on disk."""

    def __init__(self):
        self._key: bytes | None = None
        self._connections: list[dict] = []

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    @property
    def connections(self) -> list[dict]:
        return list(self._connections)

    @staticmethod
    def vault_exists() -> bool:
        return STORE_FILE.exists()

    # ── Unlock / Create ──

    def create_vault(self, master_password: str):
        """Create a new vault with the given master password."""
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16)
        self._key = _derive_key(master_password, salt)
        self._salt = salt
        self._connections = []
        self._save_to_disk(salt)

    def unlock(self, master_password: str) -> bool:
        """Attempt to unlock an existing vault. Returns True on success."""
        if not STORE_FILE.exists():
            return False
        try:
            with open(STORE_FILE, "r") as f:
                vault = json.load(f)
            salt = base64.b64decode(vault["salt"])
            nonce = base64.b64decode(vault["nonce"])
            ciphertext = base64.b64decode(vault["data"])
            key = _derive_key(master_password, salt)
            plaintext = _decrypt(nonce, ciphertext, key)
            self._connections = json.loads(plaintext.decode("utf-8"))
            self._key = key
            self._salt = salt
            return True
        except Exception:
            return False

    # ── CRUD ──

    def save(self, connections: list[dict]):
        """Save connections list (replaces all)."""
        self._connections = connections
        # Re-use existing salt or generate new one
        salt = getattr(self, "_salt", None) or os.urandom(16)
        self._salt = salt
        self._save_to_disk(salt)

    def add_connection(self, conn: dict):
        self._connections.append(conn)
        self.save(self._connections)

    def update_connection(self, index: int, conn: dict):
        if 0 <= index < len(self._connections):
            self._connections[index] = conn
            self.save(self._connections)

    def delete_connection(self, index: int):
        if 0 <= index < len(self._connections):
            self._connections.pop(index)
            self.save(self._connections)

    # ── Export / Import ──

    def export_connections(self, file_path: str, master_password: str,
                           connections: list[dict] | None = None):
        """Export connections to an encrypted .openscp file.

        Uses a fresh PBKDF2 derivation from master_password + random salt,
        so the importer only needs the master password to decrypt.
        """
        conns = connections if connections is not None else self._connections
        data = json.dumps(conns).encode("utf-8")
        salt = os.urandom(16)
        key = _derive_key(master_password, salt)
        nonce, ct = _encrypt(data, key)
        payload = {
            "version": 1,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "data": base64.b64encode(ct).decode(),
        }
        with open(file_path, "w") as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def import_connections(file_path: str, master_password: str) -> list[dict]:
        """Import connections from an .openscp file. Raises on wrong password."""
        with open(file_path, "r") as f:
            payload = json.load(f)
        salt = base64.b64decode(payload["salt"])
        key = _derive_key(master_password, salt)
        nonce = base64.b64decode(payload["nonce"])
        ciphertext = base64.b64decode(payload["data"])
        plaintext = _decrypt(nonce, ciphertext, key)
        return json.loads(plaintext.decode("utf-8"))

    # ── Internal ──

    def _save_to_disk(self, salt: bytes):
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self._connections).encode("utf-8")
        nonce, ct = _encrypt(data, self._key)
        vault = {
            "version": 1,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "data": base64.b64encode(ct).decode(),
        }
        with open(STORE_FILE, "w") as f:
            json.dump(vault, f, indent=2)

    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """Change the master password. Re-encrypts vault with new key."""
        # Verify old password works
        if not self.is_unlocked:
            if not self.unlock(old_password):
                return False
        # Derive new key and re-encrypt
        new_salt = os.urandom(16)
        self._key = _derive_key(new_password, new_salt)
        self._salt = new_salt
        self._save_to_disk(new_salt)
        return True

