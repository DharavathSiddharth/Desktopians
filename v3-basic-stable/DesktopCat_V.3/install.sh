#!/bin/bash
# Desktop Cat installer  (run ONCE; after that just launch from your app menu)

set -e
echo "==> Installing Desktop Cat..."

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/.local/share/desktop-cat"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

# 1. Core dependencies (GTK3 + Python bindings)
echo "==> Checking core dependencies..."
if ! python3 -c "import gi; gi.require_version('Gtk','3.0'); import cairo; from gi.repository import Gtk" 2>/dev/null; then
    echo "==> Installing GTK3 / PyGObject (may ask for your password)..."
    sudo apt update
    sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0
else
    echo "    Core dependencies already present."
fi

# 2. Layer Shell (lets the cat actually roam the desktop on Wayland/Cosmic)
echo "==> Installing Layer Shell support (for Wayland desktop roaming)..."
if ! python3 -c "import gi; gi.require_version('GtkLayerShell','0.1'); from gi.repository import GtkLayerShell" 2>/dev/null; then
    sudo apt install -y gir1.2-gtklayershell-0.1 2>/dev/null \
      || sudo apt install -y gir1.2-gtk-layer-shell-0.1 2>/dev/null \
      || echo "    NOTE: layer-shell package not found. The cat will still run,
             but on Wayland it may not roam. Tell me if so and I'll help."
else
    echo "    Layer Shell already present."
fi

# 3. Copy app files
echo "==> Copying application files..."
mkdir -p "$APP_DIR"
cp -f "$SRC_DIR/cat_pet.py" "$APP_DIR/"
rm -rf "$APP_DIR/assets"
cp -r "$SRC_DIR/assets" "$APP_DIR/"

# 4. Icon
mkdir -p "$ICON_DIR"
cp -f "$SRC_DIR/desktop-cat.png" "$ICON_DIR/desktop-cat.png"

# 5. Launcher (.desktop). Runs NATIVELY so Wayland layer-shell works;
#    X11 sessions fall back automatically inside the app.
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/desktop-cat.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desktop Cat
Comment=A cute pixel cat that wanders your desktop
Exec=python3 $APP_DIR/cat_pet.py
Icon=desktop-cat
Terminal=false
Categories=Utility;Toys;
StartupNotify=false
EOF
chmod +x "$DESKTOP_DIR/desktop-cat.desktop"

# 6. Refresh caches
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "==> Done!  Search 'Desktop Cat' in your app library and click to launch."
echo "    (If it doesn't appear right away, log out and back in once.)"
echo ""
echo "    Left-click + drag = pick up   |   Double-click = pet"
echo "    Right-click = menu (color, size, speed, add a friend, quit)"
