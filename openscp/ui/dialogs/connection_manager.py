"""Connection Manager dialog — CRUD + import/export for saved connections."""
from __future__ import annotations

import os
import base64
import time
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QInputDialog,
    QFileDialog, QFormLayout, QSpinBox, QComboBox, QApplication,
    QWidget,
)

from openscp.core.crypto_store import CryptoStore
from openscp.utils.i18n import tr

# ────────────────────────────────────────────────────────────────
#  Session cache
# ────────────────────────────────────────────────────────────────
_session_cache: dict = {"password": None, "expires_at": 0.0}

REMEMBER_OPTIONS_KEYS = [
    "remember.dont", "remember.15min", "remember.1hour",
    "remember.1day", "remember.1week",
]
REMEMBER_VALUES = [0, 15 * 60, 3600, 86400, 604800]


def _cache_password(password: str, duration_secs: int):
    if duration_secs > 0:
        _session_cache["password"] = password
        _session_cache["expires_at"] = time.time() + duration_secs
    else:
        _session_cache["password"] = None
        _session_cache["expires_at"] = 0.0


def _get_cached_password() -> str | None:
    if _session_cache["password"] and time.time() < _session_cache["expires_at"]:
        return _session_cache["password"]
    _session_cache["password"] = None
    return None


def _center_dialog(dialog: QDialog):
    screen = QApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - dialog.width()) // 2
        y = geo.y() + (geo.height() - dialog.height()) // 2
        dialog.move(x, y)


# ────────────────────────────────────────────────────────────────
#  Master password dialog
# ────────────────────────────────────────────────────────────────

class MasterPasswordDialog(QDialog):
    def __init__(self, is_new: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.master_pw.title"))
        self.setFixedSize(420, 280 if is_new else 240)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.is_new = is_new

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        lbl = QLabel(tr("dlg.master_pw.create") if is_new else tr("dlg.master_pw.unlock"))
        lbl.setWordWrap(True)
        lbl.setObjectName("master_pw_label")
        layout.addWidget(lbl)

        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_password.setPlaceholderText(tr("dlg.master_pw.placeholder"))
        layout.addWidget(self.input_password)

        if is_new:
            self.input_confirm = QLineEdit()
            self.input_confirm.setEchoMode(QLineEdit.EchoMode.Password)
            self.input_confirm.setPlaceholderText(tr("dlg.master_pw.confirm"))
            layout.addWidget(self.input_confirm)

        remember_row = QHBoxLayout()
        remember_lbl = QLabel(tr("dlg.master_pw.remember"))
        remember_lbl.setObjectName("remember_label")
        self.remember_combo = QComboBox()
        for key in REMEMBER_OPTIONS_KEYS:
            self.remember_combo.addItem(tr(key))
        self.remember_combo.setCurrentIndex(2)
        remember_row.addWidget(remember_lbl)
        remember_row.addWidget(self.remember_combo)
        remember_row.addStretch()
        layout.addLayout(remember_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_ok = QPushButton(tr("dlg.master_pw.btn_unlock") if not is_new else tr("dlg.master_pw.btn_create"))
        self.btn_ok.setObjectName("btn_master_pw")
        self.btn_ok.clicked.connect(self._validate)
        self.btn_cancel = QPushButton(tr("cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)
        layout.addLayout(btn_row)

        self.input_password.returnPressed.connect(self._validate)
        self.password = ""
        self.remember_duration = 0

    def showEvent(self, event):
        super().showEvent(event)
        _center_dialog(self)

    def _validate(self):
        pwd = self.input_password.text()
        if not pwd:
            QMessageBox.warning(self, tr("error"), tr("dlg.master_pw.empty"))
            return
        if self.is_new:
            if pwd != self.input_confirm.text():
                QMessageBox.warning(self, tr("error"), tr("dlg.master_pw.mismatch"))
                return
            if len(pwd) < 4:
                QMessageBox.warning(self, tr("error"), tr("dlg.master_pw.min_length"))
                return
        self.password = pwd
        self.remember_duration = REMEMBER_VALUES[self.remember_combo.currentIndex()]
        self.accept()


# ────────────────────────────────────────────────────────────────
#  Connection editor dialog (with private key support)
# ────────────────────────────────────────────────────────────────

class ConnectionEditorDialog(QDialog):
    def __init__(self, conn: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.conn_editor.edit") if conn else tr("dlg.conn_editor.new"))
        self.setFixedSize(460, 400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._private_key_b64 = conn.get("private_key", "") if conn else ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.input_name = QLineEdit(conn.get("name", "") if conn else "")
        self.input_name.setPlaceholderText("My Server")
        form.addRow(tr("dlg.conn_editor.name"), self.input_name)

        self.input_host = QLineEdit(conn.get("host", "") if conn else "")
        self.input_host.setPlaceholderText("hostname or IP")
        form.addRow(tr("dlg.conn_editor.host"), self.input_host)

        self.input_port = QSpinBox()
        self.input_port.setRange(1, 65535)
        self.input_port.setValue(conn.get("port", 22) if conn else 22)
        form.addRow(tr("dlg.conn_editor.port"), self.input_port)

        self.input_user = QLineEdit(conn.get("username", "") if conn else "")
        self.input_user.setPlaceholderText("username")
        form.addRow(tr("dlg.conn_editor.user"), self.input_user)

        self.input_pass = QLineEdit(conn.get("password", "") if conn else "")
        self.input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pass.setPlaceholderText("password")
        form.addRow(tr("dlg.conn_editor.password"), self.input_pass)

        # ── Private key ──
        key_row = QHBoxLayout()
        self.key_label = QLabel(self._key_status_text())
        self.key_label.setObjectName("key_status_label")
        key_row.addWidget(self.key_label, stretch=1)

        btn_browse = QPushButton(tr("dlg.conn_editor.key_browse"))
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self._browse_key)
        key_row.addWidget(btn_browse)

        btn_clear = QPushButton(tr("dlg.conn_editor.key_clear"))
        btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self._clear_key)
        key_row.addWidget(btn_clear)

        form.addRow(tr("dlg.conn_editor.private_key"), key_row)

        self.input_passphrase = QLineEdit(conn.get("key_passphrase", "") if conn else "")
        self.input_passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_passphrase.setPlaceholderText("optional")
        form.addRow(tr("dlg.conn_editor.key_passphrase"), self.input_passphrase)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton(tr("dlg.conn_editor.save"))
        btn_save.setObjectName("btn_save_conn")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton(tr("cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        self.result_conn = None

    def showEvent(self, event):
        super().showEvent(event)
        _center_dialog(self)

    def _key_status_text(self) -> str:
        if self._private_key_b64:
            size = len(base64.b64decode(self._private_key_b64))
            return tr("dlg.conn_editor.key_loaded", size=size)
        return tr("dlg.conn_editor.no_key")

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dlg.conn_editor.private_key"), os.path.expanduser("~/.ssh"),
            "All Files (*)"
        )
        if path:
            try:
                with open(path, "rb") as f:
                    data = f.read()
                self._private_key_b64 = base64.b64encode(data).decode("ascii")
                self.key_label.setText(self._key_status_text())
            except Exception as e:
                QMessageBox.critical(self, tr("error"), str(e))

    def _clear_key(self):
        self._private_key_b64 = ""
        self.key_label.setText(self._key_status_text())

    def _save(self):
        name = self.input_name.text().strip()
        host = self.input_host.text().strip()
        if not name or not host:
            QMessageBox.warning(self, tr("error"), tr("dlg.conn_editor.required"))
            return
        self.result_conn = {
            "name": name,
            "host": host,
            "port": self.input_port.value(),
            "username": self.input_user.text().strip(),
            "password": self.input_pass.text(),
            "private_key": self._private_key_b64,
            "key_passphrase": self.input_passphrase.text(),
        }
        self.accept()


# ────────────────────────────────────────────────────────────────
#  Connection manager dialog
# ────────────────────────────────────────────────────────────────

class ConnectionManagerDialog(QDialog):
    connect_requested = pyqtSignal(dict)

    def __init__(self, store: CryptoStore, master_password: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.conn_mgr.title"))
        self.setMinimumSize(580, 450)
        self.resize(620, 480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.store = store
        self._master_password = master_password
        self._build_ui()
        self._refresh_list()

    @staticmethod
    def open_manager(parent=None) -> ConnectionManagerDialog | None:
        store = CryptoStore()
        cached = _get_cached_password()
        if cached:
            if store.vault_exists() and store.unlock(cached):
                return ConnectionManagerDialog(store, cached, parent)

        is_new = not CryptoStore.vault_exists()
        pwd_dlg = MasterPasswordDialog(is_new, parent)
        if pwd_dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        password = pwd_dlg.password
        remember_secs = pwd_dlg.remember_duration

        if is_new:
            store.create_vault(password)
        else:
            if not store.unlock(password):
                QMessageBox.critical(parent, tr("error"), tr("dlg.master_pw.wrong"))
                return None

        _cache_password(password, remember_secs)
        return ConnectionManagerDialog(store, password, parent)

    def showEvent(self, event):
        super().showEvent(event)
        _center_dialog(self)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        title = QLabel(tr("dlg.conn_mgr.saved"))
        title.setObjectName("conn_mgr_title")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(10)

        self.conn_list = QListWidget()
        self.conn_list.setMinimumWidth(260)
        self.conn_list.itemDoubleClicked.connect(self._on_connect)
        body.addWidget(self.conn_list, stretch=1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        self.btn_connect = QPushButton(tr("dlg.conn_mgr.connect"))
        self.btn_connect.setObjectName("btn_mgr_connect")
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_add = QPushButton(tr("dlg.conn_mgr.add"))
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit = QPushButton(tr("dlg.conn_mgr.edit"))
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete = QPushButton(tr("dlg.conn_mgr.delete_btn"))
        self.btn_delete.clicked.connect(self._on_delete)

        btn_col.addWidget(self.btn_connect)
        btn_col.addSpacing(8)
        btn_col.addWidget(self.btn_add)
        btn_col.addWidget(self.btn_edit)
        btn_col.addWidget(self.btn_delete)
        btn_col.addStretch()

        sep = QWidget()
        sep.setObjectName("mgr_sep")
        sep.setFixedHeight(1)
        btn_col.addWidget(sep)

        self.btn_export = QPushButton(tr("dlg.conn_mgr.export"))
        self.btn_export.clicked.connect(self._on_export)
        self.btn_import = QPushButton(tr("dlg.conn_mgr.import"))
        self.btn_import.clicked.connect(self._on_import)
        btn_col.addWidget(self.btn_export)
        btn_col.addWidget(self.btn_import)

        body.addLayout(btn_col)
        layout.addLayout(body, stretch=1)

        hint = QLabel(tr("dlg.conn_mgr.hint"))
        hint.setObjectName("conn_mgr_hint")
        layout.addWidget(hint)

    def _refresh_list(self):
        self.conn_list.clear()
        for c in self.store.connections:
            key_icon = " 🔑" if c.get("private_key") else ""
            label = f"{c.get('name', '?')}   —   {c.get('host', '?')}:{c.get('port', 22)}{key_icon}"
            self.conn_list.addItem(QListWidgetItem(label))

    def _selected_index(self) -> int | None:
        items = self.conn_list.selectedItems()
        return self.conn_list.row(items[0]) if items else None

    def _on_connect(self):
        idx = self._selected_index()
        if idx is None:
            QMessageBox.information(self, "Select", tr("dlg.conn_mgr.select"))
            return
        self.connect_requested.emit(self.store.connections[idx])
        self.accept()

    def _on_add(self):
        dlg = ConnectionEditorDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_conn:
            self.store.add_connection(dlg.result_conn)
            self._refresh_list()

    def _on_edit(self):
        idx = self._selected_index()
        if idx is None:
            return
        dlg = ConnectionEditorDialog(self.store.connections[idx], parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_conn:
            self.store.update_connection(idx, dlg.result_conn)
            self._refresh_list()

    def _on_delete(self):
        idx = self._selected_index()
        if idx is None:
            return
        conn = self.store.connections[idx]
        reply = QMessageBox.question(
            self, tr("dlg.delete.title"),
            tr("dlg.conn_mgr.delete_confirm", name=conn.get("name", "?")),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.delete_connection(idx)
            self._refresh_list()

    def _on_export(self):
        if not self.store.connections:
            QMessageBox.information(self, "Export", tr("dlg.conn_mgr.no_conns"))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export", "connections.openscp", "OpenSCP Files (*.openscp)")
        if path:
            pwd, ok = QInputDialog.getText(self, "Export", tr("dlg.conn_mgr.export_pw"), QLineEdit.EchoMode.Password)
            if ok and pwd:
                try:
                    self.store.export_connections(path, pwd)
                    QMessageBox.information(self, "Export",
                                            tr("dlg.conn_mgr.exported", count=len(self.store.connections)))
                except Exception as e:
                    QMessageBox.critical(self, tr("error"), str(e))

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "OpenSCP Files (*.openscp)")
        if not path:
            return
        pwd, ok = QInputDialog.getText(self, "Import", tr("dlg.conn_mgr.import_pw"), QLineEdit.EchoMode.Password)
        if not ok or not pwd:
            return
        try:
            imported = CryptoStore.import_connections(path, pwd)
            existing = {c["name"] for c in self.store.connections}
            added = 0
            for c in imported:
                if c["name"] not in existing:
                    self.store.add_connection(c)
                    existing.add(c["name"])
                    added += 1
            self._refresh_list()
            QMessageBox.information(self, "Import",
                                    tr("dlg.conn_mgr.imported", added=added, total=len(imported)))
        except Exception as e:
            QMessageBox.critical(self, tr("error"), f"Failed to decrypt: {e}")
