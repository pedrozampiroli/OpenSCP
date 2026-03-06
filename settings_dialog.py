"""Settings dialog — theme, language, and master password management."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QFormLayout, QLineEdit, QMessageBox,
    QFileDialog, QApplication,
)

from i18n import tr, list_languages, set_language, get_current_language
import theme_manager
from crypto_store import CryptoStore


def _center_dialog(dialog: QDialog):
    screen = QApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - dialog.width()) // 2
        y = geo.y() + (geo.height() - dialog.height()) // 2
        dialog.move(x, y)


class SettingsDialog(QDialog):
    """Application settings: appearance + security."""

    def __init__(self, store: CryptoStore | None = None, master_password: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setFixedSize(480, 400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.store = store
        self._master_password = master_password
        self._theme_changed = False
        self._lang_changed = False

        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        _center_dialog(self)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Appearance ──
        appearance_group = QGroupBox(tr("settings.appearance"))
        appearance_layout = QFormLayout()
        appearance_layout.setSpacing(10)

        # Theme selector
        self.theme_combo = QComboBox()
        for name in theme_manager.list_themes():
            self.theme_combo.addItem(name)
        current = theme_manager.get_current_theme_name()
        idx = self.theme_combo.findText(current)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        appearance_layout.addRow(tr("settings.theme"), self.theme_combo)

        # Language selector
        self.lang_combo = QComboBox()
        languages = list_languages()
        current_lang = get_current_language()
        for code, display in languages:
            self.lang_combo.addItem(display, code)
            if code == current_lang:
                self.lang_combo.setCurrentIndex(self.lang_combo.count() - 1)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        appearance_layout.addRow(tr("settings.language"), self.lang_combo)

        # Import theme button
        btn_import_theme = QPushButton(tr("settings.import_theme"))
        btn_import_theme.clicked.connect(self._import_theme)
        appearance_layout.addRow("", btn_import_theme)

        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)

        # ── Security ──
        security_group = QGroupBox(tr("settings.security"))
        sec_layout = QVBoxLayout()
        sec_layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.input_old_pw = QLineEdit()
        self.input_old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_old_pw.setPlaceholderText(tr("settings.old_pw"))
        form.addRow(tr("settings.old_pw"), self.input_old_pw)

        self.input_new_pw = QLineEdit()
        self.input_new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_new_pw.setPlaceholderText(tr("settings.new_pw"))
        form.addRow(tr("settings.new_pw"), self.input_new_pw)

        self.input_confirm_pw = QLineEdit()
        self.input_confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_confirm_pw.setPlaceholderText(tr("settings.confirm_pw"))
        form.addRow(tr("settings.confirm_pw"), self.input_confirm_pw)

        sec_layout.addLayout(form)

        btn_change_pw = QPushButton(tr("settings.change_pw"))
        btn_change_pw.clicked.connect(self._change_password)
        sec_layout.addWidget(btn_change_pw)

        security_group.setLayout(sec_layout)
        layout.addWidget(security_group)

        layout.addStretch()

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton(tr("cancel"))
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _on_theme_changed(self, name: str):
        theme_manager.set_current_theme_name(name)
        theme = theme_manager.load_theme(name)
        qss = theme_manager.theme_to_qss(theme)
        QApplication.instance().setStyleSheet(qss)
        self._theme_changed = True

    def _on_lang_changed(self, index: int):
        code = self.lang_combo.itemData(index)
        if code:
            set_language(code)
            self._lang_changed = True

    def _import_theme(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("settings.import_theme"), "",
            "JSON Files (*.json)"
        )
        if path:
            try:
                name = theme_manager.import_theme(path)
                self.theme_combo.addItem(name)
                self.theme_combo.setCurrentText(name)
                QMessageBox.information(self, tr("settings.title"),
                                        tr("settings.theme_imported", name=name))
            except Exception as e:
                QMessageBox.critical(self, tr("error"), str(e))

    def _change_password(self):
        old_pw = self.input_old_pw.text()
        new_pw = self.input_new_pw.text()
        confirm = self.input_confirm_pw.text()

        if not old_pw or not new_pw:
            QMessageBox.warning(self, tr("error"), tr("dlg.master_pw.empty"))
            return
        if new_pw != confirm:
            QMessageBox.warning(self, tr("error"), tr("dlg.master_pw.mismatch"))
            return
        if len(new_pw) < 4:
            QMessageBox.warning(self, tr("error"), tr("dlg.master_pw.min_length"))
            return

        if not self.store:
            self.store = CryptoStore()

        # Try to unlock with old password to verify
        test_store = CryptoStore()
        if not test_store.unlock(old_pw):
            QMessageBox.critical(self, tr("error"), tr("settings.pw_wrong"))
            return

        # Re-encrypt with new password
        if test_store.change_master_password(old_pw, new_pw):
            QMessageBox.information(self, tr("settings.title"), tr("settings.pw_changed"))
            self.input_old_pw.clear()
            self.input_new_pw.clear()
            self.input_confirm_pw.clear()
        else:
            QMessageBox.critical(self, tr("error"), tr("settings.pw_wrong"))
