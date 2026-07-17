# Desktop Cat 🐈

A cute pixel-art cat that wanders around your desktop. It floats above your
windows, stays out of your way, and you can pet it, drag it, and switch between
a black and a white cat.

Built for Pop!_OS / Cosmic Desktop (runs through XWayland via GTK3).

---

## Install (one time)

1. Unzip this folder anywhere.
2. Open the folder, then run the installer **once**:

   ```bash
   ./install.sh
   ```

   (You may need: right-click `install.sh` → Properties → allow "execute",
   or run `chmod +x install.sh` first.)

That's it. **"Desktop Cat" now appears in your application menu / app library**,
with its own icon. From now on you just click it to launch — no terminal ever
again.

If it doesn't show up in the menu immediately, log out and back in once.

---

## Using it

- **Launch:** search "Desktop Cat" in your app library and click it.
- **Left-click + drag:** pick the cat up and move it; let go and it drops.
- **Right-click:** menu to switch black/white cat, make it wander, put it to
  sleep, or **Quit**.
- The cat wanders, idles, and naps on its own.

---

## Does it interfere with my work? No.

- **Click-through:** only the cat's body is clickable. The empty space around
  it passes your clicks straight through to whatever window is behind it.
- **No focus stealing:** it never grabs your keyboard or interrupts typing.
- **No taskbar clutter:** it doesn't add a window to your dock/taskbar; it just
  floats on top.

To close it, right-click the cat → **Quit**.

---

## Uninstall

```bash
./uninstall.sh
```

---

## Notes for Cosmic (Wayland)

The launcher runs the app with `GDK_BACKEND=x11` so it goes through XWayland.
That's what makes always-on-top, free positioning, and click-through work
reliably on Cosmic. If you ever see the cat sitting *behind* other windows or
not dragging smoothly, tell me — the fully-native Wayland path uses a different
mechanism (`gtk-layer-shell`) and I can build that variant.

## Customizing

Open `~/.local/share/desktop-cat/cat_pet.py` and tweak the values near the top:
`DISPLAY_SIZE` (cat size), `WALK_SPEED`, `FRAME_MS` (animation speed), etc.
