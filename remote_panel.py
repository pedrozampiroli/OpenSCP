"""Remote SFTP panel with custom model for directory listing."""
from __future__ import annotations

import stat as stat_module
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QMimeData, QByteArray, pyqtSignal, QPoint
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QDrag, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QLineEdit,
    QPushButton, QMenu, QHeaderView, QLabel, QInputDialog, QMessageBox,
)


class RemoteTreeView(QTreeView):
    """QTreeView subclass that supports drag-and-drop for SFTP files."""

    upload_drop_requested = pyqtSignal(list, str)  # (local_paths, target_remote_dir)
    download_drag_started = pyqtSignal(list)        # remote paths being dragged out

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < 10:
            super().mouseMoveEvent(event)
            return
        # Start drag with our custom mime type
        selected = self._get_selected_remote_paths()
        if not selected:
            return
        mime = QMimeData()
        data = "\n".join(selected).encode("utf-8")
        mime.setData("application/x-sftp-remote-paths", QByteArray(data))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def _get_selected_remote_paths(self) -> list[str]:
        indexes = self.selectionModel().selectedIndexes()
        paths = []
        seen = set()
        for idx in indexes:
            if idx.column() != 0:
                continue
            item = self.model().itemFromIndex(idx)
            if item and item.data(Qt.ItemDataRole.UserRole + 1) not in seen:
                full_path = item.data(Qt.ItemDataRole.UserRole + 1)
                if full_path:
                    seen.add(full_path)
                    paths.append(full_path)
        return paths

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("text/uri-list"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("text/uri-list"):
            # Highlight the folder row under the cursor
            idx = self.indexAt(event.position().toPoint())
            if idx.isValid():
                item = self.model().itemFromIndex(self.model().index(idx.row(), 0))
                if item and item.data(Qt.ItemDataRole.UserRole + 2):  # is_dir
                    self.setCurrentIndex(idx)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            local_paths = [u.toLocalFile() for u in urls if u.toLocalFile()]
            if local_paths:
                # Check if dropped on a specific folder
                target_dir = ""
                idx = self.indexAt(event.position().toPoint())
                if idx.isValid():
                    item = self.model().itemFromIndex(self.model().index(idx.row(), 0))
                    if item and item.data(Qt.ItemDataRole.UserRole + 2):  # is_dir
                        target_dir = item.data(Qt.ItemDataRole.UserRole + 1)
                self.upload_drop_requested.emit(local_paths, target_dir)
                event.acceptProposedAction()
                return
        event.ignore()


class RemotePanel(QWidget):
    """Right-side panel showing the remote SFTP filesystem."""

    download_requested = pyqtSignal(list)          # remote paths to download
    upload_requested = pyqtSignal(list, str)        # (local_paths, target_remote_dir)
    delete_requested = pyqtSignal(str, bool)   # (remote_path, is_dir)
    mkdir_requested = pyqtSignal(str)          # full remote path
    navigate_requested = pyqtSignal(str)       # remote dir path
    edit_requested = pyqtSignal(str)           # remote file to edit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = "/"
        self.sftp = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("  ⬡  REMOTE")
        title.setStyleSheet("font-weight: 700; font-size: 11px; color: #ce93d8; letter-spacing: 1.5px;")
        header.addWidget(title)
        header.addStretch()

        self.btn_up = QPushButton("⬆")
        self.btn_up.setToolTip("Go to parent directory")
        self.btn_up.setFixedSize(28, 28)
        self.btn_up.setStyleSheet("""
            QPushButton { background: #37474f; color: #e0e0e0; border: 1px solid #455a64;
                          border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background: #455a64; }
        """)
        header.addWidget(self.btn_up)

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setToolTip("Refresh")
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setStyleSheet(self.btn_up.styleSheet())
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        # ── Path bar ──
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Remote path…")
        self.path_edit.setStyleSheet("""
            QLineEdit { background: #1e272e; color: #cfd8dc; border: 1px solid #37474f;
                        border-radius: 4px; padding: 5px 8px; font-size: 12px; }
            QLineEdit:focus { border-color: #ab47bc; }
        """)
        layout.addWidget(self.path_edit)

        # ── Tree view ──
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Name", "Size", "Modified", "Permissions"])

        self.tree = RemoteTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIsDecorated(False)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self.tree.header().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setStyleSheet("""
            QTreeView {
                background: #1a2332; color: #dce6f0; border: 1px solid #2a3a4a;
                border-radius: 4px; font-size: 12px;
                selection-background-color: #6a1b9a;
            }
            QTreeView::item:hover { background: #2a2342; }
            QTreeView::branch { background: #1a2332; }
            QHeaderView::section {
                background: #212d3d; color: #90a4ae; border: none;
                padding: 4px 6px; font-size: 11px; font-weight: 600;
            }
        """)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.tree)

        # ── Signals ──
        self.tree.doubleClicked.connect(self._on_double_click)
        self.btn_up.clicked.connect(self._go_up)
        self.btn_refresh.clicked.connect(self._refresh)
        self.path_edit.returnPressed.connect(self._on_path_entered)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.upload_drop_requested.connect(lambda paths, target: self.upload_requested.emit(paths, target))

    # ── Populate ──

    def populate(self, remote_path: str, items: list):
        """Fill the model from sftp.listdir_attr() results."""
        self.current_path = remote_path
        self.path_edit.setText(remote_path)
        self.model.removeRows(0, self.model.rowCount())

        # Sort: dirs first, then files, both alphabetical
        dirs = sorted([a for a in items if stat_module.S_ISDIR(a.st_mode or 0)],
                       key=lambda a: a.filename.lower())
        files = sorted([a for a in items if not stat_module.S_ISDIR(a.st_mode or 0)],
                        key=lambda a: a.filename.lower())

        for attr in dirs + files:
            is_dir = stat_module.S_ISDIR(attr.st_mode or 0)
            icon_str = "📁" if is_dir else "📄"
            name_item = QStandardItem(f"{icon_str}  {attr.filename}")
            full_path = remote_path.rstrip("/") + "/" + attr.filename
            name_item.setData(full_path, Qt.ItemDataRole.UserRole + 1)       # full remote path
            name_item.setData(is_dir, Qt.ItemDataRole.UserRole + 2)          # is_dir flag
            name_item.setEditable(False)

            size_item = QStandardItem(self._format_size(attr.st_size) if not is_dir else "—")
            size_item.setEditable(False)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            mtime = datetime.fromtimestamp(attr.st_mtime).strftime("%Y-%m-%d %H:%M") if attr.st_mtime else "—"
            time_item = QStandardItem(mtime)
            time_item.setEditable(False)

            perm_str = stat_module.filemode(attr.st_mode) if attr.st_mode else "—"
            perm_item = QStandardItem(perm_str)
            perm_item.setEditable(False)

            self.model.appendRow([name_item, size_item, time_item, perm_item])

    @staticmethod
    def _format_size(size) -> str:
        if size is None:
            return "—"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024:
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def clear(self):
        self.model.removeRows(0, self.model.rowCount())
        self.path_edit.clear()
        self.current_path = "/"

    # ── Navigation ──

    def _on_double_click(self, index):
        item = self.model.itemFromIndex(self.model.index(index.row(), 0))
        if item and item.data(Qt.ItemDataRole.UserRole + 2):  # is_dir
            path = item.data(Qt.ItemDataRole.UserRole + 1)
            self.navigate_requested.emit(path)

    def _go_up(self):
        parent = os.path.dirname(self.current_path.rstrip("/"))
        if not parent:
            parent = "/"
        self.navigate_requested.emit(parent)

    def _refresh(self):
        self.navigate_requested.emit(self.current_path)

    def _on_path_entered(self):
        path = self.path_edit.text().strip()
        if path:
            self.navigate_requested.emit(path)

    # ── Context menu ──

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #263238; color: #eceff1; border: 1px solid #37474f; border-radius: 4px; }
            QMenu::item:selected { background: #6a1b9a; }
        """)

        idx = self.tree.indexAt(pos)
        selected_paths = self._get_selected_paths()
        selected_files = [p for p, d in selected_paths if not d]
        selected_items_all = selected_paths

        if selected_files:
            act_dl = menu.addAction("⬇  Download")
            act_dl.triggered.connect(lambda: self.download_requested.emit([p for p, _ in selected_items_all]))

            # Edit (only for single file selection)
            if len(selected_files) == 1:
                act_edit = menu.addAction("✏️  Edit")
                act_edit.triggered.connect(lambda: self.edit_requested.emit(selected_files[0]))

        if selected_items_all:
            menu.addSeparator()
            act_del = menu.addAction("🗑  Delete")
            act_del.triggered.connect(lambda: self._delete_selected(selected_items_all))

        menu.addSeparator()
        act_mkdir = menu.addAction("📁  New Folder")
        act_mkdir.triggered.connect(self._new_folder_dialog)

        act_refresh = menu.addAction("⟳  Refresh")
        act_refresh.triggered.connect(self._refresh)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _get_selected_paths(self) -> list[tuple[str, bool]]:
        """Returns list of (full_remote_path, is_dir)."""
        indexes = self.tree.selectionModel().selectedIndexes()
        result = []
        seen = set()
        for idx in indexes:
            if idx.column() != 0:
                continue
            item = self.model.itemFromIndex(idx)
            if item:
                path = item.data(Qt.ItemDataRole.UserRole + 1)
                is_dir = item.data(Qt.ItemDataRole.UserRole + 2)
                if path and path not in seen:
                    seen.add(path)
                    result.append((path, is_dir))
        return result

    def _delete_selected(self, items: list[tuple[str, bool]]):
        names = [os.path.basename(p) for p, _ in items]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(names)} item(s)?\n" + "\n".join(names[:10]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for path, is_dir in items:
                self.delete_requested.emit(path, is_dir)

    def _new_folder_dialog(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            full_path = self.current_path.rstrip("/") + "/" + name.strip()
            self.mkdir_requested.emit(full_path)
