"""Built-in text editor widget with tabs, line numbers, and basic syntax highlighting."""
from __future__ import annotations

import os
import re
import tempfile
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QRegularExpression
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QTextFormat, QSyntaxHighlighter,
    QTextCharFormat, QTextDocument, QKeySequence, QShortcut,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPlainTextEdit,
    QPushButton, QLabel, QLineEdit, QMessageBox, QTextEdit,
)

from i18n import tr


# ────────────────────────────────────────────────────────────────
#  Syntax highlighter (basic multi-language)
# ────────────────────────────────────────────────────────────────

HIGHLIGHT_RULES = {
    ".py": {
        "keywords": r"\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|yield|lambda|pass|break|continue|raise|and|or|not|in|is|True|False|None|self|async|await)\b",
        "strings": r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\'|\"[^\"\\]*(?:\\.[^\"\\]*)*\"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')',
        "comments": r'#[^\n]*',
        "numbers": r'\b\d+\.?\d*\b',
        "functions": r'\b([a-zA-Z_]\w*)\s*\(',
    },
    ".json": {
        "keys": r'"[^"]*"\s*:',
        "strings": r'"[^"]*"',
        "numbers": r'\b\d+\.?\d*\b',
        "booleans": r'\b(true|false|null)\b',
    },
    ".sh": {
        "keywords": r"\b(if|then|else|elif|fi|for|do|done|while|case|esac|function|return|exit|echo|export|source|alias|cd|ls|grep|sed|awk|cat|chmod|chown|mkdir|rm|cp|mv|sudo)\b",
        "strings": r'(\"[^\"]*\"|\'[^\']*\')',
        "comments": r'#[^\n]*',
        "variables": r'\$\{?[a-zA-Z_]\w*\}?',
    },
    ".yaml": {
        "keys": r'^[a-zA-Z_][\w.-]*\s*:',
        "strings": r'(\"[^\"]*\"|\'[^\']*\')',
        "comments": r'#[^\n]*',
        "booleans": r'\b(true|false|yes|no|null)\b',
    },
}

COLORS = {
    "keywords": "#569cd6",
    "strings": "#ce9178",
    "comments": "#6a9955",
    "numbers": "#b5cea8",
    "functions": "#dcdcaa",
    "keys": "#9cdcfe",
    "booleans": "#569cd6",
    "variables": "#4ec9b0",
}


class GenericHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: QTextDocument, rules: dict):
        super().__init__(parent)
        self._rules = []
        for category, pattern in rules.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(COLORS.get(category, "#dcdcaa")))
            if category == "comments":
                fmt.setFontItalic(True)
            if category == "keywords":
                fmt.setFontWeight(QFont.Weight.Bold)
            self._rules.append((QRegularExpression(pattern), fmt))

    def highlightBlock(self, text: str):
        for regex, fmt in self._rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


# ────────────────────────────────────────────────────────────────
#  Line number area
# ────────────────────────────────────────────────────────────────

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit with line numbers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self._update_line_area_width(0)
        font = QFont("Menlo", 13)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

    def line_number_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_area_width(self, _):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor("#1a2332"))
        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#546e7a"))
                painter.drawText(0, top, self._line_area.width() - 4,
                                 self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(block_num + 1))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_num += 1
        painter.end()


# ────────────────────────────────────────────────────────────────
#  Text editor widget (tabbed)
# ────────────────────────────────────────────────────────────────

class TextEditorWidget(QWidget):
    """Tabbed text editor. Each tab is a remote file."""

    save_requested = pyqtSignal(str, str, str)  # (remote_path, content, local_tmp)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs: dict[str, dict] = {}  # remote_path -> {editor, highlighter, local_tmp}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.setSpacing(6)

        btn_style = """
            QPushButton { padding: 4px 10px; font-size: 11px; border-radius: 3px;
                          min-width: 50px; }
        """
        self.btn_save = QPushButton(tr("editor.save"))
        self.btn_save.setStyleSheet(btn_style)
        self.btn_save.clicked.connect(self._on_save)

        self.btn_wrap = QPushButton(tr("editor.wrap"))
        self.btn_wrap.setStyleSheet(btn_style)
        self.btn_wrap.setCheckable(True)
        self.btn_wrap.clicked.connect(self._toggle_wrap)

        self.btn_close = QPushButton(tr("editor.close"))
        self.btn_close.setStyleSheet(btn_style)
        self.btn_close.clicked.connect(self._close_tab)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText(tr("editor.find_placeholder"))
        self.find_input.setMaximumWidth(200)
        self.find_input.setStyleSheet("font-size: 11px; padding: 3px 6px;")
        self.find_input.returnPressed.connect(self._find_text)

        toolbar.addWidget(self.btn_save)
        toolbar.addWidget(self.btn_wrap)
        toolbar.addWidget(self.btn_close)
        toolbar.addStretch()
        toolbar.addWidget(self.find_input)
        layout.addLayout(toolbar)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close)
        layout.addWidget(self.tab_widget)

    def open_file(self, remote_path: str, content: str, local_tmp: str):
        """Open a file in a new tab (or focus existing tab)."""
        if remote_path in self._tabs:
            idx = self.tab_widget.indexOf(self._tabs[remote_path]["editor"])
            self.tab_widget.setCurrentIndex(idx)
            return

        editor = CodeEditor()
        editor.setPlainText(content)

        # Apply syntax highlighting based on extension
        ext = os.path.splitext(remote_path)[1].lower()
        highlighter = None
        rules = HIGHLIGHT_RULES.get(ext)
        if not rules:
            for suffix in (".sh", ".bash", ".zsh"):
                if ext == suffix:
                    rules = HIGHLIGHT_RULES.get(".sh")
                    break
        if rules:
            highlighter = GenericHighlighter(editor.document(), rules)

        self._tabs[remote_path] = {
            "editor": editor,
            "highlighter": highlighter,
            "local_tmp": local_tmp,
        }
        name = os.path.basename(remote_path)
        idx = self.tab_widget.addTab(editor, name)
        self.tab_widget.setCurrentIndex(idx)

    def _on_save(self):
        editor = self.tab_widget.currentWidget()
        if not editor:
            return
        for path, info in self._tabs.items():
            if info["editor"] is editor:
                content = editor.toPlainText()
                self.save_requested.emit(path, content, info["local_tmp"])
                break

    def _toggle_wrap(self):
        editor = self.tab_widget.currentWidget()
        if editor and isinstance(editor, CodeEditor):
            if self.btn_wrap.isChecked():
                editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            else:
                editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def _close_tab(self):
        idx = self.tab_widget.currentIndex()
        if idx >= 0:
            self._on_tab_close(idx)

    def _on_tab_close(self, idx: int):
        widget = self.tab_widget.widget(idx)
        for path, info in list(self._tabs.items()):
            if info["editor"] is widget:
                del self._tabs[path]
                break
        self.tab_widget.removeTab(idx)

    def _find_text(self):
        query = self.find_input.text()
        editor = self.tab_widget.currentWidget()
        if editor and isinstance(editor, CodeEditor) and query:
            editor.find(query)

    def has_tabs(self) -> bool:
        return self.tab_widget.count() > 0
