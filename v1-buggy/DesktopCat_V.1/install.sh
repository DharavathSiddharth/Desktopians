#!/bin/bash
# Desktop Cat installer
# Installs the app so it appears in your application menu / app library.
# You only need to run this ONCE. After that, launch "Desktop Cat" like any
# normal app. No terminal needed afterwards.

set -e

echo "==> Installing Desktop Cat..."

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/.local/share/desktop-cat"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

# 1. Dependencies (GTK3 + Python bindings)
echo "==> Checking dependencies..."
if ! python3 -c "import gi; gi.require_version('Gtk','3.0'); import cairo; from gi.repository import Gtk" 2>/dev/null; then
    echo "==> Installing GTK3 / PyGObject (may ask for your password)..."
    sudo apt update
    sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0
else
    echo "    Dependencies already present."
fi

# 2. Copy app files
echo "==> Copying application files..."
mkdir -p "$APP_DIR"
cp -f "$SRC_DIR/cat_pet.py" "$APP_DIR/"
rm -rf "$APP_DIR/assets"
cp -r "$SRC_DIR/assets" "$APP_DIR/"

# 3. Install icon
mkdir -p "$ICON_DIR"
cp -f "$SRC_DIR/desktop-cat.png" "$ICON_DIR/desktop-cat.png"

# 4. Create the .desktop launcher
#    GDK_BACKEND=x11 forces XWayland so window positioning / always-on-top /
#    click-through behave correctly under Cosmic (Wayland).
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/desktop-cat.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desktop Cat
Comment=A cute pixel cat that wanders your desktop
Exec=env GDK_BACKEND=x11 python3 $APP_DIR/cat_pet.py
Icon=desktop-cat
Terminal=false
Categories=Utility;Toys;
StartupNotify=false
EOF

chmod +x "$DESKTOP_DIR/desktop-cat.desktop"

# 5. Refresh caches so it shows up immediately
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "==> Done!  'Desktop Cat' is now in your application menu / app library."
echo "    Search for 'Desktop Cat' and click it to launch."
echo "    (If it doesn't appear right away, log out and back in once.)"
echo ""
echo "    Right-click the cat for options (switch color, sleep, quit)."
echo "    Left-click and drag to pick it up."
