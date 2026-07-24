#!/bin/bash
set -e
echo "==> Removing Desktop Cat..."
rm -rf "$HOME/.local/share/desktop-cat"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/desktop-cat.png"
rm -f "$HOME/.local/share/applications/desktop-cat.desktop"
rm -f "$HOME/.config/autostart/desktop-cat.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "==> Desktop Cat removed."
