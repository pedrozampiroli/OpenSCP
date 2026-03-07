"""SSH Terminal widget — interactive shell via paramiko channel."""
from __future__ import annotations

import re
import time
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QKeyEvent
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from openscp.utils.i18n import tr
from openscp.ui.widgets.terminal_highlighter import TerminalHighlighter


class ChannelReader(QThread):
    """Background thread that reads from a paramiko channel and emits output."""
    output_received = pyqtSignal(str)
    channel_closed = pyqtSignal()

    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self._running = True

    def run(self):
        while self._running and not self.channel.closed:
            if self.channel.recv_ready():
                data = self.channel.recv(4096)
                if data:
                    self.output_received.emit(data.decode("utf-8", errors="replace"))
                else:
                    break
            elif self.channel.recv_stderr_ready():
                data = self.channel.recv_stderr(4096)
                if data:
                    self.output_received.emit(data.decode("utf-8", errors="replace"))
            else:
                time.sleep(0.05)
        self.channel_closed.emit()

    def stop(self):
        self._running = False


# ────────────────────────────────────────────────────────────────
#  ANSI / OSC / CSI escape sequence stripping
# ────────────────────────────────────────────────────────────────

# Regex that catches:
#   - OSC sequences:  ESC ] ... (BEL | ESC \)   — e.g. title setting, semantic prompts
#   - CSI sequences:  ESC [ ... final_byte       — e.g. colors, cursor, bracketed paste
#   - Simple escapes: ESC ( | ESC ) | ESC =      — charset/mode switches
#   - Also bare ] ... BEL/ESC\ without leading ESC (some terminals emit these)
#   - We NO LONGER strip \r here to handle it in the output loop
_ANSI_RE = re.compile(
    r'(?:'
    r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'  # OSC: ESC ] ... (BEL | ST)
    r'|\][^\x07\x1b]*(?:\x07|\x1b\\)'      # bare OSC without ESC (seen in some shells)
    r'|\x1b\[[0-9;?]*[a-zA-Z]'             # CSI: ESC [ params letter
    r'|\x1b[()=][0-9A-Za-z]?'              # charset / mode
    r'|\x1b\]8;[^;]*;[^\x1b\x07]*(?:\x07|\x1b\\)'  # OSC 8 hyperlinks
    r'|\x07'                                # stray BEL
    r')'
)


def strip_escape_sequences(text: str) -> str:
    """Remove all terminal escape sequences, leaving clean text."""
    return _ANSI_RE.sub('', text)


# ────────────────────────────────────────────────────────────────
#  Terminal widget
# ────────────────────────────────────────────────────────────────

class SSHTerminalWidget(QWidget):
    """Interactive SSH terminal widget.

    All keystrokes are sent directly to the shell channel for proper
    Tab completion, arrow keys, Ctrl+C, etc.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channel = None
        self._reader = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.output = TerminalTextEdit()
        self.output.key_pressed.connect(self._on_key)
        self.output.clear_requested.connect(self._clear_screen)
        font = QFont("Menlo", 13)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.output.setFont(font)
        self.highlighter = TerminalHighlighter(self.output.document())
        layout.addWidget(self.output)

    def connect_to_ssh(self, ssh_client):
        """Open an interactive shell channel on the existing SSH connection."""
        try:
            self._channel = ssh_client.invoke_shell(
                term="dumb",  # "dumb" terminal avoids most escape sequences
                width=120,
                height=40,
            )
            self._channel.settimeout(0.1)

            # Tell the shell to disable prompt extras
            self._channel.send("export TERM=dumb\n")
            self._channel.send("unset PROMPT_COMMAND\n")
            self._channel.send("alias clear='printf \"\\\\033[2J\\\\033[3J\\\\033[H\"'\n")
            self._channel.send("clear\n")

            self._reader = ChannelReader(self._channel)
            self._reader.output_received.connect(self._on_output)
            self._reader.channel_closed.connect(self._on_closed)
            self._reader.start()
            self.output.clear()
            self.output.setReadOnly(False)
            self.output.setFocus()
        except Exception as e:
            self.output.append(f"Error: {e}")

    def disconnect(self):
        if self._reader:
            self._reader.stop()
            self._reader = None
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        self.output.setReadOnly(True)

    def _on_key(self, data: bytes):
        """Send raw key data to the channel."""
        if self._channel and not self._channel.closed:
            self._channel.send(data)

    def _clear_screen(self):
        """Clear the terminal display."""
        self.output.clear()
        if self._channel and not self._channel.closed:
            self._channel.send(b"\x0c")

    def _on_output(self, text: str):
        # Detect clear screen sequences
        if any(seq in text for seq in ('\x0c', '\033[2J', '\033[3J', '\033[H')):
            self.output.clear()
            # Remove the sequences from text to avoid further processing
            for seq in ('\x0c', '\033[2J', '\033[3J', '\033[H'):
                text = text.replace(seq, '')

        clean = strip_escape_sequences(text)
        if not clean:
            return

        cursor = self.output.textCursor()

        for char in clean:
            if char == '\r':
                # Move to start of line to allow overprinting (fixes prompt duplication)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            elif char == '\n':
                # Ensure we are at the end before adding a newline
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText('\n')
            elif char == '\x08':
                # Move cursor left (standard terminal behavior)
                # If followed by a space (shell echo), it will 'delete' visually
                cursor.movePosition(QTextCursor.MoveOperation.Left)
            elif char == '\x7f':
                # Delete char at cursor
                cursor.deleteChar()
            elif char == '\x07': # Bell
                pass
            else:
                # Insert text at current cursor position
                cursor.insertText(char)

        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _on_closed(self):
        self.output.append("\n[Session closed]")
        self.output.setReadOnly(True)

    @property
    def is_connected(self) -> bool:
        return self._channel is not None and not self._channel.closed


class TerminalTextEdit(QTextEdit):
    """QTextEdit that captures keystrokes and emits them as raw bytes
    for the SSH channel, instead of inserting text locally."""

    key_pressed = pyqtSignal(bytes)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-sftp-remote-paths") or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-sftp-remote-paths") or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-sftp-remote-paths"):
            data = event.mimeData().data("application/x-sftp-remote-paths").data().decode("utf-8")
            paths = [p for p in data.split("\\n") if p]
            if paths:
                text = " ".join(f"'{p}'" for p in paths) + " "
                self.key_pressed.emit(text.encode("utf-8"))
            event.acceptProposedAction()
        elif event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
            if paths:
                text = " ".join(f"'{p}'" for p in paths) + " "
                self.key_pressed.emit(text.encode("utf-8"))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+C → interrupt
        if key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.key_pressed.emit(b"\x03")
            event.accept()
            return

        # Ctrl+D → EOF
        if key == Qt.Key.Key_D and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.key_pressed.emit(b"\x04")
            event.accept()
            return

        # Ctrl+Z → suspend
        if key == Qt.Key.Key_Z and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.key_pressed.emit(b"\x1a")
            event.accept()
            return

        # Ctrl+L → clear screen
        if key == Qt.Key.Key_L and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.clear_requested.emit()
            event.accept()
            return

        # Ctrl+W or Alt+Backspace → delete word
        is_alt_backspace = (key == Qt.Key.Key_Backspace and modifiers & Qt.KeyboardModifier.AltModifier)
        is_ctrl_w = (key == Qt.Key.Key_W and modifiers & Qt.KeyboardModifier.ControlModifier)
        if is_alt_backspace or is_ctrl_w:
            self.key_pressed.emit(b"\x17")
            event.accept()
            return

        # Ctrl+U → delete line (unix style)
        if key == Qt.Key.Key_U and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.key_pressed.emit(b"\x15")
            event.accept()
            return

        # Tab → autocomplete
        if key == Qt.Key.Key_Tab:
            self.key_pressed.emit(b"\t")
            event.accept()
            return

        # Enter / Return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.key_pressed.emit(b"\n")
            event.accept()
            return

        # Backspace
        if key == Qt.Key.Key_Backspace:
            self.key_pressed.emit(b"\x7f")
            event.accept()
            return

        # Arrow keys → ANSI escape sequences
        arrow_map = {
            Qt.Key.Key_Up: b"\x1b[A",
            Qt.Key.Key_Down: b"\x1b[B",
            Qt.Key.Key_Right: b"\x1b[C",
            Qt.Key.Key_Left: b"\x1b[D",
        }
        if key in arrow_map:
            self.key_pressed.emit(arrow_map[key])
            event.accept()
            return

        # Home / End
        if key == Qt.Key.Key_Home:
            self.key_pressed.emit(b"\x1b[H")
            event.accept()
            return
        if key == Qt.Key.Key_End:
            self.key_pressed.emit(b"\x1b[F")
            event.accept()
            return

        # Delete
        if key == Qt.Key.Key_Delete:
            self.key_pressed.emit(b"\x1b[3~")
            event.accept()
            return

        # Escape
        if key == Qt.Key.Key_Escape:
            self.key_pressed.emit(b"\x1b")
            event.accept()
            return

        # Regular text
        text = event.text()
        if text:
            self.key_pressed.emit(text.encode("utf-8"))
            event.accept()
            return
            
        super().keyPressEvent(event)
