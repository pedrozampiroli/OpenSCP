# ══════════════════════════════════════════════════════════════════
#  OpenSCP — Cross-platform build Makefile
# ══════════════════════════════════════════════════════════════════
#
#  Usage:
#    make install       Install Python dependencies
#    make run           Run the application
#    make build-mac     Build macOS .app bundle + .dmg
#    make build-linux   Build Linux binary + AppImage
#    make build-win     Build Windows .exe (run from Windows)
#    make clean         Remove build artifacts
#
# ══════════════════════════════════════════════════════════════════

APP_NAME     := OpenSCP
VERSION      := 1.0.0
ENTRY        := openscp/main.py
PYTHON       := python3
PIP          := pip3
PYINSTALLER  := $(PYTHON) -m PyInstaller

# Platform detection
UNAME_S := $(shell uname -s 2>/dev/null || echo Windows)

# Common PyInstaller args
COMMON_ARGS := \
	--name $(APP_NAME) \
	--icon="resources/icon/OpenSCPIcon.jpg" \
	--hidden-import=paramiko \
	--hidden-import=cryptography \
	--hidden-import=cffi \
	--hidden-import=nacl \
	--noconfirm

# Data paths & Execution
ifeq ($(UNAME_S),Windows)
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

.PHONY: build-win

build-win:
	$(PYINSTALLER) $(COMMON_ARGS) \
		--windowed \
		--add-data "resources/themes;resources/themes" \
		--add-data "resources/locales;resources/locales" \
		$(ENTRY)
	@echo.
	@echo ✅  Windows build complete: dist\$(APP_NAME)\$(APP_NAME).exe

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
	@echo "  make build-win     Build Windows .exe (run on Windows)"
	@echo ""
	@echo "  make clean         Remove build artifacts"
	@echo ""
