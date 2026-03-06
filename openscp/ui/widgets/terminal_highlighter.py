"""Terminal Syntax Highlighter."""
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import QRegularExpression


class TerminalHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for SSH terminal to colorize commands and outputs."""

    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        # Formats
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))  # Blue
        keyword_format.setFontWeight(QFont.Weight.Bold)

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))  # Light orange

        command_format = QTextCharFormat()
        command_format.setForeground(QColor("#4EC9B0"))  # Teal

        path_format = QTextCharFormat()
        path_format.setForeground(QColor("#DCDCAA"))  # Yellowish

        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#F44747"))  # Red
        
        prompt_format = QTextCharFormat()
        prompt_format.setForeground(QColor("#4AF626"))  # Green
        prompt_format.setFontWeight(QFont.Weight.Bold)

        # Keyword rules
        keywords = [
            "sudo", "apt", "apt-get", "yum", "dnf", "pacman", "systemctl", "service",
            "ls", "cd", "pwd", "mkdir", "rm", "mv", "cp", "cat", "echo", "grep",
            "find", "tar", "gzip", "unzip", "chmod", "chown", "ssh", "scp", "rsync",
            "python", "python3", "pip", "node", "npm", "git", "docker", "docker-compose",
            "make", "clear"
        ]
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self.highlighting_rules.append((pattern, keyword_format))

        # Shell Prompt (user@host:~$ or user@host:/path#)
        self.highlighting_rules.append((QRegularExpression(r"^[a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-\.]+:[~/\w\.\-]*[$#]"), prompt_format))
        
        # Strings (single or double quoted)
        self.highlighting_rules.append((QRegularExpression(r"\".*\""), string_format))
        self.highlighting_rules.append((QRegularExpression(r"'.*'"), string_format))

        # Paths (simple heuristic: starts with / or ./)
        self.highlighting_rules.append((QRegularExpression(r"(?<= |\b)(/|./|~/)[/\w\.\-]+"), path_format))
        
        # Errors (simple heuristic)
        self.highlighting_rules.append((QRegularExpression(r"(?i)\b(?:error|failed|denied|command not found)\b.*"), error_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
