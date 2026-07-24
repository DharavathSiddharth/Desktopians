# Desktop Cat 🐈

A cute pixel-art cat that roams your desktop. Floats above your windows, stays
out of your way, and now actually **wanders freely** on Cosmic / Wayland.

---

## Install (one time)

1. Unzip this folder.
2. Run the installer once:

   ```bash
   ./install.sh
   ```

   (If needed: `chmod +x install.sh` first, or right-click → Properties →
   allow "execute".)

After that, **"Desktop Cat" is in your app library** — just click it to launch.
No terminal ever again. If it doesn't show up immediately, log out and back in.

---

## Controls

- **Left-click + drag** — pick the cat up; let go and it drops/falls.
- **Double-click** — pet it (happy wiggle + a little heart).
- **Right-click** — full menu:
  - **Black cat / White cat** — switch color
  - **Size** — Small / Medium / Large
  - **Animation speed** — Slow / Normal / Fast / Very Fast
  - **Wander / Zoomies! / Sleep** — trigger behaviors on demand
  - **Add a friend** — spawn another cat (make a whole clowder!)
  - **Shoo this cat** — remove just this one
  - **Pause** — freeze in place
  - **Start on login** — auto-launch when you log in
  - **Quit all cats** — close everything

---

## Surprises 🎁

- **Thought bubbles** — the cat occasionally goes "meow", "mrrp", "~", "?".
- **Catnaps** — after loitering a while it may curl up and sleep (with z z z).
- **Zoomies** — every so often it suddenly dashes across the screen. You can
  also trigger this yourself from the menu.
- **Friends** — spawn as many cats as you like; each wanders on its own.

---

## Why it roams now (the fix)

Wayland (which Cosmic uses) does not let an app set its own window position —
so the previous version's cat animated in place but couldn't move. This version
uses the **Layer Shell** Wayland protocol (via `gtk-layer-shell`), the proper
mechanism for desktop widgets to position and move themselves. The app
auto-detects your session:

- **Wayland + Layer Shell available** → free roaming via layer-shell.
- **X11** → falls back to normal window moves.

The installer installs the layer-shell library for you.

---

## Stays out of your way

- **Click-through:** only the cat's body is clickable; clicks on the empty
  space around it pass through to the window behind.
- **No focus stealing:** it never grabs your keyboard.
- **No taskbar clutter.**

---

## Uninstall

```bash
./uninstall.sh
```

## Customize

Edit `~/.local/share/desktop-cat/cat_pet.py` — tunables (sizes, speeds, tick
rate, etc.) are near the top.
