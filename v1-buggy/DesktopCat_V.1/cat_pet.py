#!/usr/bin/env python3
"""
Desktop Cat - a shimeji-style animated cat that wanders your screen.

Designed to stay completely out of your way:
  * Click-through: only the cat itself is clickable; empty space around it
    passes clicks to whatever window is behind.
  * Never steals keyboard focus.
  * No taskbar entry, floats above your windows.

Interactions:
  * Left-click + drag  -> pick the cat up; release to drop it (it falls).
  * Right-click        -> menu (switch color, wander, sleep, quit).
"""

import os
import random
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import cairo

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# ---- Tunables ----
DISPLAY_SIZE = 110      # on-screen size of the cat in pixels
FRAME_MS = 180          # ms between animation frames
TICK_MS = 33            # physics tick (~30 fps)
WALK_SPEED = 2          # px per tick while walking
GRAVITY = 2             # px per tick added while falling
IDLE_MIN_MS, IDLE_MAX_MS = 3000, 7000
WALK_MIN_MS, WALK_MAX_MS = 2000, 5000
GROUND_MARGIN = 40      # how far above the very bottom the cat rests
ALPHA_THRESHOLD = 30    # pixels more transparent than this are click-through

FRAME_COUNTS = {"idle": 3, "walk": 4, "sleep": 3, "happy": 3}


def build_input_region(pixbuf):
    """Build a cairo.Region covering only the non-transparent pixels of a
    pixbuf. Used as the window's input shape so transparent areas are
    click-through."""
    w, h = pixbuf.get_width(), pixbuf.get_height()
    region = cairo.Region()
    if not pixbuf.get_has_alpha():
        region.union(cairo.RectangleInt(0, 0, w, h))
        return region
    pixels = pixbuf.get_pixels()
    stride = pixbuf.get_rowstride()
    nch = pixbuf.get_n_channels()
    for y in range(h):
        x = 0
        while x < w:
            if pixels[y * stride + x * nch + 3] > ALPHA_THRESHOLD:
                start = x
                while x < w and pixels[y * stride + x * nch + 3] > ALPHA_THRESHOLD:
                    x += 1
                region.union(cairo.RectangleInt(start, y, x - start, 1))
            else:
                x += 1
    return region


class DesktopCat(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        self.color = "black"
        self.frames = {}       # color -> state -> [pixbuf]
        self.regions = {}      # color -> state -> [cairo.Region]
        self.load_assets()

        self.state = "idle"
        self.frame_index = 0
        self.idle_streak = 0
        self.direction = random.choice([-1, 1])
        self.dragging = False
        self.drag_offset = (0, 0)
        self.vy = 0

        screen = Gdk.Screen.get_default()
        self.screen_w = screen.get_width()
        self.screen_h = screen.get_height()

        # ---- Window: unobtrusive floating overlay ----
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)          # never steal keyboard focus
        self.set_resizable(False)
        self.set_app_paintable(True)
        self.set_default_size(DISPLAY_SIZE, DISPLAY_SIZE)
        self.stick()                           # show on all workspaces

        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(DISPLAY_SIZE, DISPLAY_SIZE)
        self.add(self.area)

        self.area.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("realize", self.on_realize)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )

        self.x = random.randint(0, max(0, self.screen_w - DISPLAY_SIZE))
        self.y = self.screen_h - DISPLAY_SIZE - GROUND_MARGIN
        self.move(self.x, self.y)

        self.show_all()

        GLib.timeout_add(FRAME_MS, self.on_animation_tick)
        GLib.timeout_add(TICK_MS, self.on_physics_tick)
        self.schedule_next_behavior()

    def on_realize(self, *_):
        self.apply_input_shape()

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------
    def load_assets(self):
        for color in ("black", "white"):
            folder = os.path.join(ASSET_DIR, color)
            fr, rg = {}, {}
            for state, count in FRAME_COUNTS.items():
                pbs = []
                for i in range(count):
                    path = os.path.join(folder, f"{state}_{i}.png")
                    pb = GdkPixbuf.Pixbuf.new_from_file(path)
                    pb = pb.scale_simple(DISPLAY_SIZE, DISPLAY_SIZE,
                                         GdkPixbuf.InterpType.BILINEAR)
                    pbs.append(pb)
                fr[state] = pbs
            # walk_right = mirror of walk
            fr["walk_left"] = fr["walk"]
            fr["walk_right"] = [p.flip(True) for p in fr["walk"]]
            fr["fall"] = [fr["happy"][0]]
            # precompute click-through regions per frame
            for state, pbs in fr.items():
                rg[state] = [build_input_region(p) for p in pbs]
            self.frames[color] = fr
            self.regions[color] = rg

    def cur_pixbuf(self):
        seq = self.frames[self.color][self.state]
        return seq[self.frame_index % len(seq)]

    def cur_region(self):
        seq = self.regions[self.color][self.state]
        return seq[self.frame_index % len(seq)]

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def on_draw(self, widget, cr):
        cr.set_operator(cairo.Operator.CLEAR)
        cr.paint()
        cr.set_operator(cairo.Operator.OVER)
        Gdk.cairo_set_source_pixbuf(cr, self.cur_pixbuf(), 0, 0)
        cr.paint()
        return False

    def apply_input_shape(self):
        win = self.get_window()
        if win is not None:
            win.input_shape_combine_region(self.cur_region(), 0, 0)

    def redraw(self):
        self.area.queue_draw()
        self.apply_input_shape()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def set_state(self, state):
        self.state = state
        self.frame_index = 0
        self.redraw()

    def on_animation_tick(self):
        if self.state != "fall":
            self.frame_index += 1
        self.redraw()
        return True

    # ------------------------------------------------------------------
    # Movement / physics
    # ------------------------------------------------------------------
    def on_physics_tick(self):
        if self.dragging:
            return True
        ground_y = self.screen_h - DISPLAY_SIZE - GROUND_MARGIN

        if self.state == "fall":
            self.vy += GRAVITY
            self.y += self.vy
            if self.y >= ground_y:
                self.y = ground_y
                self.vy = 0
                self.set_state("idle")
                self.schedule_next_behavior()
            self.move(self.x, self.y)

        elif self.state in ("walk_left", "walk_right"):
            self.x += WALK_SPEED * self.direction
            if self.x <= 0:
                self.x = 0
                self.direction = 1
                self.set_state("walk_right")
            elif self.x >= self.screen_w - DISPLAY_SIZE:
                self.x = self.screen_w - DISPLAY_SIZE
                self.direction = -1
                self.set_state("walk_left")
            self.move(self.x, self.y)
        return True

    # ------------------------------------------------------------------
    # Behavior scheduler
    # ------------------------------------------------------------------
    def schedule_next_behavior(self):
        if self.dragging:
            return
        if self.state == "sleep":
            GLib.timeout_add(random.randint(4000, 9000), self._wake)
        elif self.state in ("walk_left", "walk_right"):
            GLib.timeout_add(random.randint(WALK_MIN_MS, WALK_MAX_MS), self._end_walk)
        else:  # idle
            self.idle_streak += 1
            GLib.timeout_add(random.randint(IDLE_MIN_MS, IDLE_MAX_MS), self._end_idle)

    def _end_idle(self):
        if self.dragging:
            return False
        if self.idle_streak >= 3 and random.random() < 0.4:
            self.idle_streak = 0
            self.set_state("sleep")
        else:
            self.direction = random.choice([-1, 1])
            self.set_state("walk_left" if self.direction < 0 else "walk_right")
        self.schedule_next_behavior()
        return False

    def _end_walk(self):
        if self.dragging:
            return False
        self.set_state("idle")
        self.schedule_next_behavior()
        return False

    def _wake(self):
        if self.dragging:
            return False
        self.idle_streak = 0
        self.set_state("idle")
        self.schedule_next_behavior()
        return False

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------
    def on_button_press(self, widget, event):
        if event.button == 1:
            self.dragging = True
            self.drag_offset = (event.x, event.y)
            self.set_state("happy")
        elif event.button == 3:
            self.show_menu(event)
        return True

    def on_motion(self, widget, event):
        if self.dragging:
            rx, ry = self.get_position()
            self.x = rx + int(event.x - self.drag_offset[0])
            self.y = ry + int(event.y - self.drag_offset[1])
            self.move(self.x, self.y)
        return True

    def on_button_release(self, widget, event):
        if event.button == 1 and self.dragging:
            self.dragging = False
            self.vy = 0
            self.set_state("fall")
        return True

    # ------------------------------------------------------------------
    # Right-click menu
    # ------------------------------------------------------------------
    def show_menu(self, event):
        menu = Gtk.Menu()

        def item(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", cb)
            menu.append(mi)

        item("Black cat", lambda w: self.switch_color("black"))
        item("White cat", lambda w: self.switch_color("white"))
        menu.append(Gtk.SeparatorMenuItem())
        item("Wander", lambda w: self.force("walk"))
        item("Sleep", lambda w: self.force("sleep"))
        menu.append(Gtk.SeparatorMenuItem())
        item("Quit", lambda w: Gtk.main_quit())

        menu.show_all()
        menu.popup_at_pointer(event)

    def switch_color(self, color):
        self.color = color
        self.frame_index = 0
        self.redraw()

    def force(self, kind):
        if kind == "walk":
            self.direction = random.choice([-1, 1])
            self.set_state("walk_left" if self.direction < 0 else "walk_right")
        elif kind == "sleep":
            self.set_state("sleep")
        self.schedule_next_behavior()


def main():
    cat = DesktopCat()
    cat.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()
