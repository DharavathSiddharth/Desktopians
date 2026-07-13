# 🐾 Desktopians

> Tiny pixel critters that live on your desktop, wander around, take naps, get
> the zoomies, and demand to be petted. And the whole thing is **yours to hack.**

Made by **Dharavath Siddharth** · Amrita Vishwa Vidyapeetham · open source, forever.

---

## 👋 Hey, welcome in

This is **Desktopians** — a little desktop-pet app. A cute animated character
(a cat! a penguin! a fire-breathing dragon! a Pop!_OS bot!) hangs out on your
screen, floats over your windows, and generally vibes while you work.

But here's the actual point: **this code is open. Break it. Rebuild it. Make it
weird.** Change how fast they walk, add your own characters, invent new
behaviors, spawn 50 of them at once. There are no rules except *have fun*.

Fork it, mess with it, show your friends what you made. That's the whole idea.

---

## ✨ What it does

- Wanders around your desktop on its own 🚶
- Random **catnaps** 😴, cute **thought bubbles** 💬, and sudden **zoomies** 💨
- **Drag** it anywhere with the mouse 🖱️
- **Double-click** to pet it (it gets a lil' heart) 💗
- **Right-click** for a menu: switch character, size, animation speed, add a
  friend, pause, quit
- **Click-through**: only the critter's body is clickable — clicks on empty
  space go to whatever's behind it, so it never blocks your work
- Never steals your keyboard, no taskbar clutter

Comes with several characters: **black cat, white cat, Charizard-style dragon,
penguin, and two Pop!_OS bots.**

---

## 🚀 Get it running

You'll need Linux with Python 3 (works great on Pop!_OS / Cosmic).

```bash
git clone <this-repo>
cd desktopians
./install.sh        # run once — installs it into your app menu
```

Then just search **"Desktop Cat"** in your app library and click it. Done.
(The installer sets up GTK + layer-shell for you.)

To remove: `./uninstall.sh`

---

## 🔧 Mess with it — the 2-minute tour

Everything lives in **`cat_pet.py`**. Open it, scroll to the top, and you'll
find a block of settings you can just... change. Here's the fun stuff:

| Want to... | Change this | Try |
|---|---|---|
| Make them faster/slower | `SPEEDS` list | add `("Ludicrous", 40, 4.0)` |
| Change their size | `SIZES` dict | add `"Huge": 220` |
| Change frame rate | `TICK_MS` | `16` = 60fps buttery smooth |
| Walk speed | `BASE_WALK_SPEED` | `5` = speed demon |
| How high they sit | `GROUND_MARGIN` | `0` = right at the edge |
| Nap frequency | in `_cb_end_idle()` | lower the `0.4` |
| Zoomies chance | in `_cb_end_idle()` | change `0.88` → `0.6` |
| What bubbles say | in `_cb_random_bubble()` | edit the word list! |

**How it works in one breath:** a timer fires ~30×/sec (`on_tick`), which
advances the animation frame and moves the critter. A little state machine
(`idle → walk → sleep → zoomies...`) decides what it does next on random timers.
Drawing is done with cairo. That's basically it. Go poke at it.

> 🧠 Want to go deeper — or rewrite it in **C / C++**? There's a full
> **`ENGINEER_GUIDE.txt`** that maps every part of the code to its C/C++
> equivalent, step by step. It's a proper engineer's reference.

---

## 🎨 Make your OWN character

This is the best part. You can add any critter you dream up. Two steps:

### Step 1 — Generate a sprite sheet (with any AI image generator)

Paste this prompt into Gemini / an image AI:

```
Create a pixel-art sprite sheet of a cute chibi [YOUR CHARACTER] for a game,
in clean 16-bit SNES style, on a SINGLE SOLID FLAT pure magenta (#FF00FF)
background.

CRITICAL:
- Background must be ONE flat magenta color. NOT transparent, NO checkerboard,
  NO gridlines or boxes between frames.
- Every frame same size, evenly spaced, aligned to a grid.
- In every frame the character is the SAME size, centered, feet on the SAME
  baseline (so it animates without jitter). Whole character inside its cell.

POSES (each pose on its own row, left to right):
- Row 1 — Idle: 3 frames (subtle movement, front-facing)
- Row 2 — Walk: 4 frames, SIDE PROFILE facing LEFT, clean walk cycle
- Row 3 — Sleep: 3 frames (curled up, eyes closed)
- Row 4 — Happy: 3 frames (content / smiling)

STYLE: crisp flat pixel art, no blur, no anti-aliasing, simple dark outline,
identical lighting in every frame. No text, no extra icons.
```

The **magenta background** is the secret sauce — it's a color no critter uses,
so it can be cleanly removed by code.

### Step 2 — Turn the image into an assets folder

Save this as `make_assets.py`, drop your sprite sheet next to it, and run it.
It removes the magenta, auto-finds each frame, centers them, and spits out a
ready-to-use folder.

```python
# make_assets.py  — usage: python3 make_assets.py yoursheet.png yourname
import sys, os, numpy as np
from PIL import Image
from scipy import ndimage

path, name = sys.argv[1], sys.argv[2]
img = Image.open(path).convert('RGB'); arr = np.array(img).astype(int)
r,g,b = arr[:,:,0],arr[:,:,1],arr[:,:,2]
bg = (r>180)&(g<120)&(b>180)                       # detect magenta
rgba = np.dstack([arr[:,:,0],arr[:,:,1],arr[:,:,2],np.where(bg,0,255)]).astype('uint8')
lbl,_ = ndimage.label(ndimage.binary_opening(~bg, iterations=1))
boxes=[[s[1].start,s[0].start,s[1].stop,s[0].stop] for s in ndimage.find_objects(lbl)
       if s and (lbl[s]==lbl[s].max()).sum()>800]
boxes.sort(key=lambda x:(x[1]+x[3])/2)             # top-to-bottom
rows=[]; cur=[boxes[0]]
for x in boxes[1:]:
    (cur if abs((x[1]+x[3])/2-(cur[-1][1]+cur[-1][3])/2)<80 else rows.append(sorted(cur,key=lambda b:b[0])) or cur.clear() or cur).append(x)
rows.append(sorted(cur,key=lambda b:b[0]))
C=int(np.percentile([max(b[2]-b[0],b[3]-b[1]) for r in rows for b in r],95))+16
os.makedirs(f'assets/{name}',exist_ok=True)
plan={'idle':(0,3),'walk':(1,4),'sleep':(2,3),'happy':(3,3)}
for state,(ri,n) in plan.items():
    for i,bx in enumerate(rows[ri][:n]):
        x0,y0,x1,y1=bx; s=Image.fromarray(rgba[y0:y1,x0:x1],'RGBA')
        cv=Image.new('RGBA',(C,C),(0,0,0,0))
        cv.paste(s,((C-s.width)//2,C-s.height-12),s)
        cv.save(f'assets/{name}/{state}_{i}.png')
print(f'Done! -> assets/{name}/')
```

(Needs `pip install pillow numpy scipy`.)

### Step 3 — Add it to the app (2 tiny edits in `cat_pet.py`)

```python
# 1. add your name to the character loops (in _load_sources AND _rebuild_scaled):
for color in ("black", "white", "yourname"):

# 2. add a menu button (in _menu):
simple("Your Character", lambda w: self._set_color("yourname"))
```

Relaunch → right-click → there's your critter. 🎉

---

## 🧬 The Lineage Chain (important + kinda cool)

Desktopians is passed like a torch. When you fork it, you **add one line** to
**`LINEAGE.md`** recording who you forked from. Never delete old lines — only
add yours.

This builds an unbroken chain: Gen 0 (me) → Gen 1 → Gen 2 → ... so *any* version
can be traced all the way back to the origin, blockchain-style. It's how we keep
the family tree of everyone who ever hacked on this. See `LICENSE` + `LINEAGE.md`.

---

## 📜 License

**MIT License** — do basically anything: use it, change it, share it, even for
free projects of your own. The only rules: keep the original credit (that's me,
Dharavath Siddharth), and keep the lineage chain going. Full text in `LICENSE`.

---

## 💛 Go build something silly

Seriously — fork it, make a dancing character, add sound, make them fight, make
them fall in love, whatever. Share what you made. That's the whole point.

*Have fun. — Siddharth*
