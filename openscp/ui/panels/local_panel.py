"""Local filesystem panel with QTreeView + QFileSystemModel."""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QMimeData, QUrl, pyqtSignal, QModelIndex
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QAction, QIcon, QFileSystemModel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QLineEdit,
    QPushButton, QMenu, QHeaderView, QLabel,
)


class LocalTreeView(QTreeView):
    """QTreeView subclass that supports dropping remote files onto it."""

    file_drop_requested = pyqtSignal(list)  # list of remote paths encoded in mime

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-sftp-remote-paths"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-sftp-remote-paths"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasFormat("application/x-sftp-remote-paths"):
            data = event.mimeData().data("application/x-sftp-remote-paths").data().decode("utf-8")
            paths = [p for p in data.split("\n") if p]
            self.file_drop_requested.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class LocalPanel(QWidget):
    """Left-side panel showing the local filesystem."""

    upload_requested = pyqtSignal(list)         # local paths to upload
    download_requested = pyqtSignal(list)        # remote paths dropped here

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("  ⬡  LOCAL")
        title.setObjectName("local_panel_title")
        header.addWidget(title)
        header.addStretch()

        self.btn_up = QPushButton("⬆")
        self.btn_up.setToolTip("Go to parent directory")
        self.btn_up.setFixedSize(28, 28)
        header.addWidget(self.btn_up)

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setToolTip("Refresh")
        self.btn_refresh.setFixedSize(28, 28)
        header.addWidget(self.btn_refresh)

        layout.addLayout(header)

        from openscp.ui.widgets.breadcrumb_navigator import BreadcrumbNavigator
        # ── Path bar ──
        self.path_edit = BreadcrumbNavigator()
        layout.addWidget(self.path_edit)

        # ── Tree view ──
        self.model = QFileSystemModel()
        self.model.setRootPath("")
        self.model.setFilter(
            self.model.filter() | self.model.filter().AllDirs | self.model.filter().Files
        )

        self.tree = LocalTreeView()
        self.tree.setModel(self.model)
        home = str(Path.home())
        idx = self.model.index(home)
        self.tree.setRootIndex(idx)
        self.path_edit.set_path(home, is_remote=False)
        self.current_path = home

        # Show only relevant columns: Name, Size, Date Modified
        self.tree.hideColumn(2)  # Type
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 3):
            self.tree.header().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        
        self.tree.setAnimated(False)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        layout.addWidget(self.tree)

        # ── Signals ──
        self.tree.doubleClicked.connect(self._on_double_click)
        self.btn_up.clicked.connect(self._go_up)
        self.btn_refresh.clicked.connect(self._refresh)
        self.path_edit.path_entered.connect(self._on_path_entered)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.file_drop_requested.connect(lambda paths: self.download_requested.emit(paths))

    # ── Navigation ──

    def _navigate_to(self, path: str):
        if os.path.isdir(path):
            self.current_path = path
            idx = self.model.index(path)
            self.tree.setRootIndex(idx)
            self.path_edit.set_path(path, is_remote=False)

    def _on_double_click(self, index: QModelIndex):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self._navigate_to(path)

    def _go_up(self):
        parent = os.path.dirname(self.current_path)
        if parent and parent != self.current_path:
            self._navigate_to(parent)

    def _refresh(self):
        self._navigate_to(self.current_path)

    def _on_path_entered(self, path: str):
        path = path.strip()
        if os.path.isdir(path):
            self._navigate_to(path)

    # ── Context menu ──

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        indexes = self.tree.selectionModel().selectedIndexes()
        # Filter to column-0 only
        paths = list({self.model.filePath(i) for i in indexes if i.column() == 0})
        file_paths = [p for p in paths if os.path.isfile(p)]

        if file_paths:
            act_upload = menu.addAction("⬆  Upload to remote")
            act_upload.triggered.connect(lambda: self.upload_requested.emit(file_paths))

        act_refresh = menu.addAction("⟳  Refresh")
        act_refresh.triggered.connect(self._refresh)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ── Helpers ──

    def selected_file_paths(self) -> list[str]:
        indexes = self.tree.selectionModel().selectedIndexes()
        paths = list({self.model.filePath(i) for i in indexes if i.column() == 0})
        return [p for p in paths if os.path.isfile(p)]
