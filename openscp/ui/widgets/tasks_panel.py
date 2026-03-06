"""Background Tasks panel to display active and finished background jobs."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QProgressBar
)
from openscp.utils.i18n import tr


class TaskItemWidget(QWidget):
    """A custom widget to represent a single task in the list."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.label_title = QLabel(title)
        self.label_title.setStyleSheet("font-weight: bold;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(200)

        self.label_status = QLabel(tr("status.connecting"))
        self.label_status.setFixedWidth(120)
        self.label_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.label_title, stretch=1)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.label_status)

    def set_progress(self, current: int, total: int):
        if total > 0:
            pct = int(current * 100 / total)
            self.progress_bar.setValue(pct)
            self.label_status.setText(f"{pct}%")
        else:
            self.progress_bar.setMaximum(0)  # indeterminate
            self.label_status.setText(tr("status.connecting"))

    def set_finished(self, msg: str):
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)
        self.label_status.setText(msg)
        self.label_title.setStyleSheet("color: #4caf50; font-weight: bold;")

    def set_error(self, msg: str):
        self.label_status.setText("Error")
        self.label_title.setText(self.label_title.text() + f" - {msg}")
        self.label_title.setStyleSheet("color: #f44336; font-weight: bold;")


class TasksPanelWidget(QWidget):
    """A panel to show all background processes running."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = {}  # worker -> QListWidgetItem

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setStyleSheet("""
            QListWidget { background: #1e272e; border: none; }
            QListWidget::item { border-bottom: 1px solid #37474f; padding: 2px; }
        """)
        
        layout.addWidget(self.list_widget)

    @pyqtSlot(object, str)
    def add_task(self, worker, title: str):
        """Add a new task item representing a worker."""
        item = QListWidgetItem(self.list_widget)
        widget = TaskItemWidget(title)
        
        item.setSizeHint(widget.sizeHint())
        self.list_widget.setItemWidget(item, widget)
        
        self._tasks[worker] = (item, widget)

    @pyqtSlot(object, int, int)
    def update_task_progress(self, worker, current: int, total: int):
        """Update progress bar for a specific worker."""
        if worker in self._tasks:
            _, widget = self._tasks[worker]
            widget.set_progress(current, total)

    @pyqtSlot(object, str)
    def complete_task(self, worker, msg: str = "Done"):
        """Mark task as finished."""
        if worker in self._tasks:
            _, widget = self._tasks[worker]
            widget.set_finished(msg)

    @pyqtSlot(object, str)
    def error_task(self, worker, msg: str):
        """Mark task as errored."""
        if worker in self._tasks:
            _, widget = self._tasks[worker]
            widget.set_error(msg)
