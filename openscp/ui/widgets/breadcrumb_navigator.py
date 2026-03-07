"""Dolphin-style breadcrumb navigation widget."""
from __future__ import annotations

import os
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit, QStackedWidget, QLabel

class BreadcrumbNavigator(QStackedWidget):
    """A breadcrumb navigator that shows clickable path segments.
    Double-clicking the widget switches to a standard QLineEdit."""

    path_entered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)

        self._current_path = ""
        self._is_remote = False

        # Page 0: Breadcrumbs
        self.breadcrumb_container = QWidget()
        self.breadcrumb_container.setObjectName("breadcrumb_container")
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_container)
        self.breadcrumb_layout.setContentsMargins(4, 2, 4, 2)
        self.breadcrumb_layout.setSpacing(0)
        self.breadcrumb_container.installEventFilter(self)

        # Page 1: Line Edit
        self.path_edit = QLineEdit()
        self.path_edit.setObjectName("path_edit_navigator")
        self.path_edit.setPlaceholderText("Enter path...")
        self.path_edit.returnPressed.connect(self._on_return_pressed)
        
        # Override focus out to switch back
        self.path_edit.focusOutEvent = self._on_edit_focus_out

        self.addWidget(self.breadcrumb_container)
        self.addWidget(self.path_edit)

    def eventFilter(self, obj, event):
        if obj == self.breadcrumb_container and event.type() == QEvent.Type.MouseButtonDblClick:
            self._start_editing()
            return True
        return super().eventFilter(obj, event)

    def set_path(self, path: str, is_remote: bool = False):
        self._current_path = path
        self._is_remote = is_remote
        self.path_edit.setText(path)
        self._build_breadcrumbs()
        self.setCurrentIndex(0)

    def _start_editing(self):
        self.setCurrentIndex(1)
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def _on_return_pressed(self):
        new_path = self.path_edit.text()
        self.setCurrentIndex(0)
        if new_path != self._current_path:
            self.path_entered.emit(new_path)

    def _on_edit_focus_out(self, event):
        self.setCurrentIndex(0)
        QLineEdit.focusOutEvent(self.path_edit, event)

    def _build_breadcrumbs(self):
        # Clear layout
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sep = "/" if self._is_remote else os.sep
        
        # Parse path into segments
        if self._is_remote:
            parts = [p for p in self._current_path.split(sep) if p]
            root_text = "/"
            root_path = "/"
        else:
            if os.name == 'nt':
                parts = [p for p in self._current_path.split(sep) if p]
                root_text = parts[0] + sep if parts else "C:\\"
                root_path = root_text
                if parts: parts.pop(0)
            else:
                parts = [p for p in self._current_path.split(sep) if p]
                root_text = "/"
                root_path = "/"

        # Create root button
        btn_root = QPushButton(root_text)
        btn_root.setObjectName("breadcrumb_btn")
        btn_root.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_root.clicked.connect(lambda _, p=root_path: self.path_entered.emit(p))
        self.breadcrumb_layout.addWidget(btn_root)

        current_build = root_path
        if not current_build.endswith(sep):
            current_build += sep

        for part in parts:
            lbl_sep = QLabel("›")
            lbl_sep.setObjectName("breadcrumb_sep")
            self.breadcrumb_layout.addWidget(lbl_sep)

            btn = QPushButton(part)
            btn.setObjectName("breadcrumb_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            current_build += part
            target_path = current_build
            btn.clicked.connect(lambda _, p=target_path: self.path_entered.emit(p))
            
            self.breadcrumb_layout.addWidget(btn)
            current_build += sep

        self.breadcrumb_layout.addStretch()
