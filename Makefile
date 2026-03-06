# ══════════════════════════════════════════════════════════════════
#  OpenSCP — Cross-platform build Makefile
# ══════════════════════════════════════════════════════════════════
#
#  Usage:
#    make install       Install Python dependencies
#    make run           Run the application
#    make build-mac     Build macOS .app bundle + .dmg
#    make build-linux   Build Linux binary + AppImage
#    make build-win     Build Windows .exe (auto-detects .venv)
#    make clean         Remove build artifacts
#
#  Windows: Works with CMD, PowerShell, Git Bash, MSYS2, etc.
#           Automatically uses .venv if available, otherwise global Python
#
# ══════════════════════════════════════════════════════════════════

APP_NAME     := OpenSCP
VERSION      := 1.0.0
ENTRY        := openscp/main.py
PYTHON       := python3
PIP          := pip3
PYINSTALLER  := $(PYTHON) -m PyInstaller

# Platform detection - detects Windows, MinGW, MSYS, Cygwin
UNAME_S := $(shell uname -s 2>/dev/null || echo Windows)

# Check if we're on Windows (including Git Bash, MSYS, MinGW, Cygwin)
IS_WINDOWS := $(if $(or $(findstring Windows,$(UNAME_S)),$(findstring MINGW,$(UNAME_S)),$(findstring MSYS,$(UNAME_S)),$(findstring CYGWIN,$(UNAME_S))),yes,no)

# Default Python commands
ifeq ($(IS_WINDOWS),yes)
  # Check for .venv using test command (works in Git Bash/MSYS)
  VENV_EXISTS := $(shell test -d .venv && echo yes)
  
  # Prefer .venv if it exists, otherwise use global Python
  ifeq ($(VENV_EXISTS),yes)
    PYTHON := .venv/Scripts/python.exe
    PIP    := .venv/Scripts/pip.exe
  else
    PYTHON := python
    PIP    := pip
  endif
else
  PYTHON := python3
  PIP    := pip3
endif

PYINSTALLER  := $(PYTHON) -m PyInstaller

# Common PyInstaller args
COMMON_ARGS := \
	--name $(APP_NAME) \
	--icon="resources/icon/OpenSCPIcon.jpg" \
	--hidden-import=paramiko \
	--hidden-import=cryptography \
	--hidden-import=cffi \
	--hidden-import=nacl \
	--noconfirm

# Data paths (use : on Unix, ; on Windows)
ifeq ($(IS_WINDOWS),yes)
  DATA_SEP := ;
  PYTHONPATH_CMD := set PYTHONPATH=.&&
else
  DATA_SEP := :
  PYTHONPATH_CMD := PYTHONPATH=.
endif

# ──────────────────────────────────────────────────────────────────
#  General
# ──────────────────────────────────────────────────────────────────

.PHONY: install run clean lint

install:
	$(PIP) install -r requirements.txt
	$(PIP) install pyinstaller Pillow

run:
	$(PYTHONPATH_CMD) $(PYTHON) -m openscp.main

clean:
	rm -rf build/ dist/ *.spec __pycache__ .eggs *.egg-info
	rm -f $(APP_NAME).dmg
	rm -f icon.png
	rm -rf $(APP_NAME).AppDir

lint:
	$(PYTHON) -c "import py_compile, glob; files = glob.glob('openscp/**/*.py', recursive=True); [py_compile.compile(f, doraise=True) for f in files]; print(f'✓ {len(files)} files OK')"

# ──────────────────────────────────────────────────────────────────
#  macOS — .app bundle + .dmg
# ──────────────────────────────────────────────────────────────────

.PHONY: build-mac dmg

build-mac:
	$(PYINSTALLER) $(COMMON_ARGS) \
		--windowed \
		--add-data "resources/themes:resources/themes" \
		--add-data "resources/locales:resources/locales" \
		--osx-bundle-identifier com.openscp.app \
		$(ENTRY)
	@echo ""
	@echo "✅  macOS build complete: dist/$(APP_NAME).app"

dmg: build-mac
	@echo "Creating DMG..."
	@rm -f $(APP_NAME).dmg
	@if command -v create-dmg >/dev/null 2>&1; then \
		create-dmg \
			--volname "$(APP_NAME)" \
			--window-size 600 400 \
			--app-drop-link 450 200 \
			"$(APP_NAME).dmg" \
			"dist/$(APP_NAME).app"; \
	else \
		hdiutil create -volname "$(APP_NAME)" \
			-srcfolder "dist/$(APP_NAME).app" \
			-ov -format UDZO \
			"$(APP_NAME).dmg"; \
	fi
	@echo "✅  DMG created: $(APP_NAME).dmg"

# ──────────────────────────────────────────────────────────────────
#  Linux — onefile binary + AppImage
# ──────────────────────────────────────────────────────────────────

.PHONY: build-linux appimage

build-linux:
	$(PYINSTALLER) $(COMMON_ARGS) \
		--onefile \
		--add-data "resources/themes:resources/themes" \
		--add-data "resources/locales:resources/locales" \
		$(ENTRY)
	@echo ""
	@echo "✅  Linux build complete: dist/$(APP_NAME)"

appimage: build-linux
	@echo "Creating AppImage..."
	@rm -rf $(APP_NAME).AppDir
	mkdir -p $(APP_NAME).AppDir/usr/bin
	mkdir -p $(APP_NAME).AppDir/usr/share/applications
	mkdir -p $(APP_NAME).AppDir/usr/share/icons/hicolor/256x256/apps
	cp dist/$(APP_NAME) $(APP_NAME).AppDir/usr/bin/
	@echo '[Desktop Entry]' > $(APP_NAME).AppDir/usr/share/applications/$(APP_NAME).desktop
	@echo 'Name=$(APP_NAME)' >> $(APP_NAME).AppDir/usr/share/applications/$(APP_NAME).desktop
	@echo 'Exec=$(APP_NAME)' >> $(APP_NAME).AppDir/usr/share/applications/$(APP_NAME).desktop
	@echo 'Icon=$(APP_NAME)' >> $(APP_NAME).AppDir/usr/share/applications/$(APP_NAME).desktop
	@echo 'Type=Application' >> $(APP_NAME).AppDir/usr/share/applications/$(APP_NAME).desktop
	@echo 'Categories=Network;FileTransfer;' >> $(APP_NAME).AppDir/usr/share/applications/$(APP_NAME).desktop
	cp $(APP_NAME).AppDir/usr/share/applications/$(APP_NAME).desktop $(APP_NAME).AppDir/
	@# Convert JPG to PNG for AppImage icon
	@if [ ! -f icon.png ]; then \
		$(PYTHON) -c "from PyQt6.QtGui import QGuiApplication, QImage; app = QGuiApplication([]); QImage('resources/icon/OpenSCPIcon.jpg').save('icon.png')"; \
	fi
	cp icon.png $(APP_NAME).AppDir/usr/share/icons/hicolor/256x256/apps/$(APP_NAME).png
	cp icon.png $(APP_NAME).AppDir/$(APP_NAME).png
	@# Create AppRun
	@echo '#!/bin/bash' > $(APP_NAME).AppDir/AppRun
	@echo 'HERE="$$(dirname "$$(readlink -f "$$0")")"' >> $(APP_NAME).AppDir/AppRun
	@echo 'exec "$$HERE/usr/bin/$(APP_NAME)" "$$@"' >> $(APP_NAME).AppDir/AppRun
	chmod +x $(APP_NAME).AppDir/AppRun
	@# Package with appimagetool if available
	@if command -v appimagetool >/dev/null 2>&1; then \
		ARCH=$$(uname -m) appimagetool $(APP_NAME).AppDir $(APP_NAME)-$(VERSION)-$$(uname -m).AppImage; \
		echo "✅  AppImage created: $(APP_NAME)-$(VERSION)-$$(uname -m).AppImage"; \
	else \
		echo "⚠  appimagetool not found. AppDir ready at $(APP_NAME).AppDir/"; \
		echo "   Install: https://github.com/AppImage/AppImageKit/releases"; \
	fi

# ──────────────────────────────────────────────────────────────────
#  Windows — .exe (run this from Windows cmd/powershell)
# ──────────────────────────────────────────────────────────────────

.PHONY: build-win build-win-venv build-win-global

# Smart build: uses .venv if available, otherwise global Python
# Use build-win-venv or build-win-global to override
build-win:
ifeq ($(IS_WINDOWS),yes)
	@echo ""
	@echo "═══════════════════════════════════════════════════════════="
	@echo " OpenSCP - Build para Windows"
	@echo "═══════════════════════════════════════════════════════════="
ifeq ($(VENV_EXISTS),yes)
	@echo " Usando Python do ambiente virtual (.venv)"
else
	@echo " Usando Python global do sistema"
endif
	@echo "═══════════════════════════════════════════════════════════="
	@echo ""
endif
	$(PYINSTALLER) $(COMMON_ARGS) \
		--windowed \
		--add-data "resources/themes;resources/themes" \
		--add-data "resources/locales;resources/locales" \
		$(ENTRY)
ifeq ($(IS_WINDOWS),yes)
	@echo ""
	@echo "✅ Build completo: dist/$(APP_NAME)/$(APP_NAME).exe"
else
	@echo ""
	@echo "✅  Windows build complete: dist/$(APP_NAME)/$(APP_NAME).exe"
endif

# Explicit build with .venv Python
build-win-venv:
	@echo ""
	@echo "Usando Python do ambiente virtual (.venv)..."
	@echo ""
	.venv/Scripts/python.exe -m PyInstaller $(COMMON_ARGS) \
		--windowed \
		--add-data "themes;themes" \
		--add-data "locales;locales" \
	$(ENTRY)
	@echo ""
	@echo "✅ Build completo: dist/$(APP_NAME)/$(APP_NAME).exe"

# Explicit build with global Python
build-win-global:
	@echo ""
	@echo "Usando Python global do sistema..."
	@echo ""
	python -m PyInstaller $(COMMON_ARGS) \
		--windowed \
		--add-data "themes;themes" \
		--add-data "locales;locales" \
	$(ENTRY)
	@echo ""
	@echo "✅ Build completo: dist/$(APP_NAME)/$(APP_NAME).exe"

# ──────────────────────────────────────────────────────────────────
#  Help
# ──────────────────────────────────────────────────────────────────

.PHONY: help

help:
	@echo ""
	@echo "  ⬡ OpenSCP Build System"
	@echo "  ━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  make install       Install Python dependencies"
	@echo "  make run           Run the application"
	@echo "  make lint          Syntax-check all .py files"
	@echo ""
	@echo "  make build-mac     Build macOS .app bundle"
	@echo "  make dmg           Build macOS .app + .dmg"
	@echo ""
	@echo "  make build-linux   Build Linux onefile binary"
	@echo "  make appimage      Build Linux AppImage"
	@echo ""
	@echo "  make build-win          Build Windows .exe (auto-detecta .venv)"
	@echo "  make build-win-venv     Build Windows .exe (força uso do .venv)"
	@echo "  make build-win-global   Build Windows .exe (força Python global)"
	@echo ""
	@echo "  make clean         Remove build artifacts"
	@echo ""
