#!/usr/bin/env python3
"""
Desktop Cat - a shimeji-style animated cat that wanders your screen.

Movement works two ways, auto-detected:
  * Wayland (Cosmic, Sway, KDE, ...): uses the Layer Shell protocol so the cat
    can actually roam the desktop and be dragged anywhere.
  * X11: falls back to normal window moves.

Stays out of your way: click-through (only the cat body is clickable), never
steals keyboard focus, no taskbar entry.

Interactions:
  * Left-click + drag  -> pick the cat up; release to drop it (it falls).
  * Double-click       -> pet it (happy wiggle + heart).
  * Right-click        -> menu: color, size, animation speed, add a friend,
                          start-on-login, pause, quit.

Surprises: random thought bubbles, catnaps, and sudden "zoomies" dashes.
"""

import os
import random
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import cairo

# ---- Optional: Layer Shell (Wayland-native positioning) ----
LAYER_SHELL_AVAILABLE = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    LAYER_SHELL_AVAILABLE = True
except (ValueError, ImportError):
    LAYER_SHELL_AVAILABLE = False

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SCRIPT_PATH = os.path.abspath(__file__)

# ---- Constants ----
TICK_MS = 33                     # single master tick (~30 fps)
BUBBLE_H = 46                    # headroom above the cat for thought bubbles
GROUND_MARGIN = 40
ALPHA_THRESHOLD = 30
FRAME_COUNTS = {"idle": 3, "walk": 4, "sleep": 3, "happy": 3}

SIZES = {"Small": 80, "Medium": 110, "Large": 150}
DEFAULT_SIZE = "Medium"

# speed presets: (frame_ms, walk multiplier)
SPEEDS = [
    ("Slow", 280, 0.6),
    ("Normal", 180, 1.0),
    ("Fast", 110, 1.6),
    ("Very Fast", 70, 2.4),
]
DEFAULT_SPEED = 1                # index into SPEEDS
BASE_WALK_SPEED = 2

AUTOSTART_PATH = os.path.join(
    os.path.expanduser("~/.config/autostart"), "desktop-cat.desktop"
)


def build_region(pixbuf):
    """cairo.Region of the opaque pixels of a pixbuf (for click-through)."""
    w, h = pixbuf.get_width(), pixbuf.get_height()
    region = cairo.Region()
    if not pixbuf.get_has_alpha():
        region.union(cairo.RectangleInt(0, 0, w, h))
        return region
    px = pixbuf.get_pixels()
    stride = pixbuf.get_rowstride()
    nch = pixbuf.get_n_channels()
    for y in range(h):
        x = 0
        while x < w:
            if px[y * stride + x * nch + 3] > ALPHA_THRESHOLD:
                s = x
                while x < w and px[y * stride + x * nch + 3] > ALPHA_THRESHOLD:
                    x += 1
                region.union(cairo.RectangleInt(s, y, x - s, 1))
            else:
                x += 1
    return region


class DesktopCat(Gtk.Window):
    instances = set()

    def __init__(self, color="black", size_name=DEFAULT_SIZE):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        DesktopCat.instances.add(self)

        self.color = color
        self.size_name = size_name
        self.display_size = SIZES[self.size_name]
        self.speed_idx = DEFAULT_SPEED
        self.frame_ms = SPEEDS[self.speed_idx][1]
        self.walk_mult = SPEEDS[self.speed_idx][2]

        self.src = {}       # color -> state -> [native pixbuf]
        self._load_sources()
        self.frames = {}    # color -> state -> [scaled pixbuf]
        self.regions = {}   # color -> state -> [region]
        self._rebuild_scaled()

        self.state = "idle"
        self.frame_index = 0
        self.anim_accum = 0
        self.tick_count = 0
        self.idle_streak = 0
        self.direction = random.choice([-1, 1])
        self.speed_boost = 1.0
        self.dragging = False
        self.grab = (0, 0)
        self.vy = 0
        self.paused = False
        self.behavior_token = 0
        self.bubble = None            # (kind, text)
        self.bubble_expire = 0

        # environment / backend detection
        disp = Gdk.Display.get_default()
        self.is_wayland = "Wayland" in type(disp).__name__
        self.use_layer = self.is_wayland and LAYER_SHELL_AVAILABLE

        # screen size from the primary monitor
        mon = disp.get_primary_monitor() or disp.get_monitor(0)
        geo = mon.get_geometry()
        self.screen_w, self.screen_h = geo.width, geo.height

        self._setup_window()

        self.x = random.randint(0, max(0, self.screen_w - self.display_size))
        self.y = self.screen_h - self.display_size - BUBBLE_H - GROUND_MARGIN

        if self.use_layer:
            self._init_layer_shell()

        self.show_all()
        self._apply_position()

        GLib.timeout_add(TICK_MS, self.on_tick)
        self._schedule_next()

    # ------------------------------------------------------------------
    # Window / backend setup
    # ------------------------------------------------------------------
    def _setup_window(self):
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_resizable(False)
        self.set_app_paintable(True)
        self.stick()

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self.area = Gtk.DrawingArea()
        self._resize_area()
        self.add(self.area)

        self.area.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("realize", lambda *_: self._apply_input_shape())
        self.connect("destroy", self._on_destroy)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )

    def _resize_area(self):
        self.area.set_size_request(self.display_size, self.display_size + BUBBLE_H)
        self.set_default_size(self.display_size, self.display_size + BUBBLE_H)

    def _init_layer_shell(self):
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "desktop-cat")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, int(self.x))
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, int(self.y))

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------
    def _load_sources(self):
        for color in ("black", "white"):
            folder = os.path.join(ASSET_DIR, color)
            d = {}
            for state, count in FRAME_COUNTS.items():
                d[state] = [
                    GdkPixbuf.Pixbuf.new_from_file(
                        os.path.join(folder, f"{state}_{i}.png")
                    )
                    for i in range(count)
                ]
            self.src[color] = d

    def _rebuild_scaled(self):
        sz = self.display_size
        for color in ("black", "white"):
            fr, rg = {}, {}
            for state, pbs in self.src[color].items():
                fr[state] = [
                    p.scale_simple(sz, sz, GdkPixbuf.InterpType.BILINEAR) for p in pbs
                ]
            fr["walk_left"] = fr["walk"]
            fr["walk_right"] = [p.flip(True) for p in fr["walk"]]
            fr["fall"] = [fr["happy"][0]]
            for state, pbs in fr.items():
                rg[state] = [build_region(p) for p in pbs]
            self.frames[color] = fr
            self.regions[color] = rg

    def _cur_pixbuf(self):
        seq = self.frames[self.color][self.state]
        return seq[self.frame_index % len(seq)]

    def _cur_region(self):
        seq = self.regions[self.color][self.state]
        return seq[self.frame_index % len(seq)]

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def on_draw(self, widget, cr):
        cr.set_operator(cairo.Operator.CLEAR)
        cr.paint()
        cr.set_operator(cairo.Operator.OVER)
        Gdk.cairo_set_source_pixbuf(cr, self._cur_pixbuf(), 0, BUBBLE_H)
        cr.paint()
        if self.bubble:
            self._draw_bubble(cr)
        return False

    def _draw_bubble(self, cr):
        kind, text = self.bubble
        cx = self.display_size / 2
        cy = BUBBLE_H / 2
        if kind == "heart":
            self._heart(cr, cx, 8, 22, (0.90, 0.20, 0.30))
            return
        # text bubble: rounded white rect + text
        cr.select_font_face("Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(15)
        ext = cr.text_extents(text)
        pad = 8
        bw = ext.width + pad * 2
        bh = ext.height + pad * 2
        bx = cx - bw / 2
        by = cy - bh / 2
        self._round_rect(cr, bx, by, bw, bh, 8)
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, 0.7)
        cr.set_line_width(1.5)
        cr.stroke()
        cr.set_source_rgb(0.1, 0.1, 0.1)
        cr.move_to(cx - ext.width / 2 - ext.x_bearing,
                   cy - ext.height / 2 - ext.y_bearing)
        cr.show_text(text)

    @staticmethod
    def _round_rect(cr, x, y, w, h, r):
        import math
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        cr.close_path()

    @staticmethod
    def _heart(cr, cx, top, s, color):
        cr.save()
        cr.translate(cx - s / 2, top)
        cr.scale(s, s)
        cr.move_to(0.5, 0.25)
        cr.curve_to(0.5, 0.0, 0.0, 0.0, 0.0, 0.35)
        cr.curve_to(0.0, 0.65, 0.5, 0.85, 0.5, 1.05)
        cr.curve_to(0.5, 0.85, 1.0, 0.65, 1.0, 0.35)
        cr.curve_to(1.0, 0.0, 0.5, 0.0, 0.5, 0.25)
        cr.close_path()
        cr.set_source_rgb(*color)
        cr.fill()
        cr.restore()

    def _apply_input_shape(self):
        win = self.get_window()
        if win is not None:
            win.input_shape_combine_region(self._cur_region(), 0, BUBBLE_H)

    def _redraw(self):
        self.area.queue_draw()
        self._apply_input_shape()

    def _apply_position(self):
        if self.use_layer:
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, int(self.x))
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, int(self.y))
        else:
            self.move(int(self.x), int(self.y))

    # ------------------------------------------------------------------
    # State + master tick
    # ------------------------------------------------------------------
    def _set_state(self, state):
        self.state = state
        self.frame_index = 0
        self._redraw()

    def _show_bubble(self, kind, text="", secs=2.2):
        self.bubble = (kind, text)
        self.bubble_expire = self.tick_count + int(secs * 1000 / TICK_MS)

    def on_tick(self):
        if self.paused:
            return True
        self.tick_count += 1
        self.anim_accum += TICK_MS
        if self.anim_accum >= self.frame_ms:
            self.anim_accum = 0
            if self.state != "fall":
                self.frame_index += 1
        self._move_step()
        if self.bubble and self.tick_count >= self.bubble_expire:
            self.bubble = None
        self._redraw()
        return True

    def _move_step(self):
        if self.dragging:
            return
        ground = self.screen_h - self.display_size - BUBBLE_H - GROUND_MARGIN
        if self.state == "fall":
            self.vy += 2
            self.y += self.vy
            if self.y >= ground:
                self.y = ground
                self.vy = 0
                self._set_state("idle")
                self._schedule_next()
            self._apply_position()
        elif self.state in ("walk_left", "walk_right"):
            speed = BASE_WALK_SPEED * self.walk_mult * self.speed_boost
            self.x += speed * self.direction
            if self.x <= 0:
                self.x = 0
                self.direction = 1
                self._set_state("walk_right")
            elif self.x >= self.screen_w - self.display_size:
                self.x = self.screen_w - self.display_size
                self.direction = -1
                self._set_state("walk_left")
            self._apply_position()

    # ------------------------------------------------------------------
    # Behavior scheduling (token guards prevent overlapping timers)
    # ------------------------------------------------------------------
    def _schedule_next(self):
        if self.dragging:
            return
        self.behavior_token += 1
        tok = self.behavior_token
        if self.state == "sleep":
            self._show_bubble("text", "z z z", secs=3)
            GLib.timeout_add(random.randint(4000, 9000), self._cb_wake, tok)
        elif self.state in ("walk_left", "walk_right"):
            GLib.timeout_add(random.randint(2000, 5000), self._cb_end_walk, tok)
        else:  # idle
            self.idle_streak += 1
            GLib.timeout_add(random.randint(3000, 7000), self._cb_end_idle, tok)
            if random.random() < 0.35:
                GLib.timeout_add(random.randint(600, 2500), self._cb_random_bubble, tok)

    def _cb_end_idle(self, tok):
        if tok != self.behavior_token or self.dragging:
            return False
        roll = random.random()
        if self.idle_streak >= 3 and roll < 0.35:
            self.idle_streak = 0
            self._set_state("sleep")
        elif roll > 0.88:
            self._start_zoomies()
            return False
        else:
            self.direction = random.choice([-1, 1])
            self._set_state("walk_left" if self.direction < 0 else "walk_right")
        self._schedule_next()
        return False

    def _cb_end_walk(self, tok):
        if tok != self.behavior_token or self.dragging:
            return False
        self.speed_boost = 1.0
        self._set_state("idle")
        self._schedule_next()
        return False

    def _cb_wake(self, tok):
        if tok != self.behavior_token or self.dragging:
            return False
        self.idle_streak = 0
        self._set_state("idle")
        self._schedule_next()
        return False

    def _cb_random_bubble(self, tok):
        if tok != self.behavior_token or self.dragging or self.bubble:
            return False
        if self.state in ("walk_left", "walk_right", "idle"):
            self._show_bubble("text", random.choice(["meow", "mrrp", "~", "?"]))
        return False

    def _start_zoomies(self):
        self.behavior_token += 1
        tok = self.behavior_token
        self.speed_boost = 3.2
        self.direction = random.choice([-1, 1])
        self._set_state("walk_left" if self.direction < 0 else "walk_right")
        self._show_bubble("text", "!", secs=1.4)
        GLib.timeout_add(1400, self._cb_end_zoomies, tok)

    def _cb_end_zoomies(self, tok):
        if tok != self.behavior_token or self.dragging:
            return False
        self.speed_boost = 1.0
        self._set_state("idle")
        self._schedule_next()
        return False

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------
    def on_button_press(self, widget, event):
        if event.button == 1:
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self._pet()
                return True
            self.dragging = True
            # Use absolute root-screen coords so 1 pixel of mouse move = 1 pixel
            # of cat move, regardless of how the window shifts underneath.
            self._drag_root_x = event.x_root
            self._drag_root_y = event.y_root
            self._drag_cat_x  = self.x
            self._drag_cat_y  = self.y
            self.behavior_token += 1
            self._set_state("happy")
        elif event.button == 3:
            self._menu(event)
        return True

    def on_motion(self, widget, event):
        if self.dragging:
            # Delta from original click in stable screen space
            dx = event.x_root - self._drag_root_x
            dy = event.y_root - self._drag_root_y
            self.x = self._drag_cat_x + dx
            self.y = self._drag_cat_y + dy
            self.x = max(-self.display_size / 2,
                         min(self.screen_w - self.display_size / 2, self.x))
            self.y = max(-BUBBLE_H,
                         min(self.screen_h - self.display_size / 2, self.y))
            self._apply_position()
        return True

    def on_button_release(self, widget, event):
        if event.button == 1 and self.dragging:
            self.dragging = False
            self.vy = 0
            self._set_state("fall")
        return True

    def _pet(self):
        self.behavior_token += 1
        tok = self.behavior_token
        self.dragging = False
        self._set_state("happy")
        self._show_bubble("heart", secs=1.6)
        GLib.timeout_add(1200, self._cb_end_pet, tok)

    def _cb_end_pet(self, tok):
        if tok != self.behavior_token or self.dragging:
            return False
        self._set_state("idle")
        self._schedule_next()
        return False

    # ------------------------------------------------------------------
    # Right-click menu
    # ------------------------------------------------------------------
    def _menu(self, event):
        menu = Gtk.Menu()

        def simple(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", cb)
            menu.append(mi)

        def submenu(label, options, current, cb):
            parent = Gtk.MenuItem(label=label)
            sub = Gtk.Menu()
            first = None
            for i, opt in enumerate(options):
                mi = Gtk.RadioMenuItem(label=opt)
                if first is None:
                    first = mi
                else:
                    mi.join_group(first)
                mi.set_active(i == current)
                mi.connect("toggled", cb, i)
                sub.append(mi)
            parent.set_submenu(sub)
            menu.append(parent)

        # color
        simple("Black cat", lambda w: self._set_color("black"))
        simple("White cat", lambda w: self._set_color("white"))
        menu.append(Gtk.SeparatorMenuItem())

        # size
        submenu("Size", list(SIZES.keys()),
                list(SIZES.keys()).index(self.size_name), self._on_size)
        # animation speed
        submenu("Animation speed", [s[0] for s in SPEEDS],
                self.speed_idx, self._on_speed)
        menu.append(Gtk.SeparatorMenuItem())

        # actions
        simple("Wander", lambda w: self._force("walk"))
        simple("Zoomies!", lambda w: self._start_zoomies())
        simple("Sleep", lambda w: self._force("sleep"))
        menu.append(Gtk.SeparatorMenuItem())

        simple("Add a friend", lambda w: self._add_friend())
        simple("Shoo this cat", lambda w: self._shoo())

        pause = Gtk.CheckMenuItem(label="Pause")
        pause.set_active(self.paused)
        pause.connect("toggled", self._on_pause)
        menu.append(pause)

        autostart = Gtk.CheckMenuItem(label="Start on login")
        autostart.set_active(os.path.exists(AUTOSTART_PATH))
        autostart.connect("toggled", self._on_autostart)
        menu.append(autostart)

        menu.append(Gtk.SeparatorMenuItem())
        simple("Quit all cats", lambda w: Gtk.main_quit())

        menu.show_all()
        menu.popup_at_pointer(event)

    # ---- menu callbacks ----
    def _set_color(self, color):
        self.color = color
        self.frame_index = 0
        self._redraw()

    def _on_size(self, item, idx):
        if not item.get_active():
            return
        self.size_name = list(SIZES.keys())[idx]
        self.display_size = SIZES[self.size_name]
        self._rebuild_scaled()
        self._resize_area()
        self._redraw()

    def _on_speed(self, item, idx):
        if not item.get_active():
            return
        self.speed_idx = idx
        self.frame_ms = SPEEDS[idx][1]
        self.walk_mult = SPEEDS[idx][2]

    def _force(self, kind):
        self.behavior_token += 1
        self.speed_boost = 1.0
        if kind == "walk":
            self.direction = random.choice([-1, 1])
            self._set_state("walk_left" if self.direction < 0 else "walk_right")
        elif kind == "sleep":
            self._set_state("sleep")
        self._schedule_next()

    def _on_pause(self, item):
        self.paused = item.get_active()

    def _on_autostart(self, item):
        if item.get_active():
            os.makedirs(os.path.dirname(AUTOSTART_PATH), exist_ok=True)
            with open(AUTOSTART_PATH, "w") as f:
                f.write(
                    "[Desktop Entry]\nType=Application\nName=Desktop Cat\n"
                    f"Exec=python3 {SCRIPT_PATH}\nIcon=desktop-cat\n"
                    "Terminal=false\nX-GNOME-Autostart-enabled=true\n"
                )
        else:
            if os.path.exists(AUTOSTART_PATH):
                os.remove(AUTOSTART_PATH)

    def _add_friend(self):
        DesktopCat(color=random.choice(["black", "white"]),
                   size_name=self.size_name)

    def _shoo(self):
        self.destroy()

    def _on_destroy(self, *_):
        DesktopCat.instances.discard(self)
        if not DesktopCat.instances:
            Gtk.main_quit()


def main():
    DesktopCat(color="black")
    Gtk.main()


if __name__ == "__main__":
    main()
