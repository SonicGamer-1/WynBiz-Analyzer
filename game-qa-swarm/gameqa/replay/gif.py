"""Replay + GIF rendering.

The GIF is *re-simulated* from (seed, actions), not recorded during the run.
That keeps it byte-for-byte consistent with the repro file and means a replay
can be regenerated at any time -- including after a fix, for the before/after
comparison.

Pillow only. If Pillow is missing, make_gif returns None and the dashboard
falls back to an ASCII frame slider over the recorded trace, so cutting the
GIF costs nothing.
"""
from __future__ import annotations

from ..game.actions import normalise
from ..game.grid_game import GridGame

CELL = 48
PALETTE = {
    "#": (( 44,  49,  62), ( 74,  82, 102)),   # wall
    ".": (( 28,  32,  42), ( 48,  56,  74)),   # floor
    "~": ((  9,  11,  20), ( 59, 130, 246)),   # pit
    "C": (( 28,  32,  42), (251, 191,  36)),   # coin
    "K": (( 28,  32,  42), (251, 191,  36)),   # key
    "D": (( 92,  51,  23), ( 71,  85, 105)),   # door
    "G": (( 16, 185, 129), (110, 231, 183)),   # goal
    "E": (( 28,  32,  42), (220,  38,  38)),   # enemy
    "@": (( 28,  32,  42), ( 37,  99, 235)),   # player
    "W": (( 28,  32,  42), (251, 191,  36)),   # player on goal (won)
}


def simulate(seed, actions, max_steps=None):
    """Re-run (seed, actions) and return (frames, findings_actions, env).

    frames[i] is the ASCII board *after* step i; frames[0] is the start state.
    """
    env = GridGame()
    env.reset(int(seed))
    frames = [env.render_state()]
    limit = len(actions) if max_steps is None else min(len(actions), max_steps)
    for i in range(limit):
        action = normalise(actions[i])
        try:
            _obs, _reward, done, _info = env.step(action)
        except Exception as exc:                        # noqa: BLE001
            frames.append(
                env.render_state()
                + "\n!! %s: %s" % (type(exc).__name__, exc)
            )
            break
        frames.append(env.render_state())
        if done:
            break
    return frames


def has_pillow():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _draw_hud(draw, width, hud_height, grid_lines, error_text=""):
    draw.rectangle((0, 0, width, hud_height), fill=(15, 18, 26))
    draw.line((0, hud_height - 1, width, hud_height - 1), fill=(38, 45, 60), width=1)

    coins = sum(row.count("C") for row in grid_lines)
    has_key_on_map = any("K" in row for row in grid_lines)
    won = any("W" in row for row in grid_lines)

    title = "GAME ENVIRONMENT · THE CRYPT"
    draw.text((12, 11), title, fill=(203, 213, 225))

    status = "VICTORY" if won else ("CRASH" if error_text else "RUNNING")
    status_col = (52, 211, 153) if won else ((239, 68, 68) if error_text else (148, 163, 184))

    draw.text((width // 2 - 50, 11), "COINS: %d" % coins, fill=(251, 191, 36))
    draw.text((width // 2 + 35, 11), "KEY: " + ("WORLD" if has_key_on_map else "HELD"),
              fill=(167, 139, 250) if not has_key_on_map else (148, 163, 184))
    draw.text((width - 95, 11), "STATUS: " + status, fill=status_col)


def _draw_tile(draw, ch, box):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    w = x1 - x0

    if ch == "#":
        # 3D Dungeon Masonry Stone Wall
        draw.rectangle(box, fill=(44, 49, 62))
        draw.line((x0, y0, x1, y0), fill=(74, 82, 102), width=3)
        draw.line((x0, y0, x0, y1), fill=(60, 68, 86), width=2)
        draw.line((x0, y1 - 1, x1, y1 - 1), fill=(22, 25, 34), width=3)
        draw.line((x1 - 1, y0, x1 - 1, y1), fill=(28, 32, 42), width=2)
        mid_y = y0 + w // 2
        draw.line((x0, mid_y, x1, mid_y), fill=(30, 34, 44), width=1)
        mid_x = x0 + w // 2
        draw.line((mid_x, y0, mid_x, mid_y), fill=(30, 34, 44), width=1)
        draw.line((x0 + w // 4, mid_y, x0 + w // 4, y1), fill=(30, 34, 44), width=1)
        draw.line((x0 + 3 * w // 4, mid_y, x0 + 3 * w // 4, y1), fill=(30, 34, 44), width=1)
        return

    # Floor base for items and actors
    draw.rectangle(box, fill=(28, 32, 42))
    draw.rectangle((x0 + 1, y0 + 1, x1 - 1, y1 - 1), outline=(37, 43, 56), width=1)
    draw.point((cx, cy), fill=(48, 56, 74))

    if ch == "~":
        # Hazard Abyss Pit
        draw.rectangle(box, fill=(9, 11, 20))
        draw.arc((x0 + 4, cy - 6, x1 - 4, cy + 6), 0, 180, fill=(59, 130, 246), width=2)
        draw.arc((x0 + 8, cy - 2, x1 - 8, cy + 8), 180, 360, fill=(37, 99, 235), width=2)

    elif ch == "C":
        # Shimmering Bevelled Gold Coin
        r = 13
        draw.ellipse((cx - r + 1, cy - r + 3, cx + r + 1, cy + r + 3), fill=(15, 18, 25))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(251, 191, 36), outline=(217, 119, 6), width=2)
        draw.ellipse((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), outline=(245, 158, 11), width=1)
        draw.rectangle((cx - 5, cy - 5, cx - 2, cy - 2), fill=(255, 255, 230))

    elif ch == "K":
        # Golden Skeleton Key
        r = 8
        draw.ellipse((cx - r + 1, cy - r - 3, cx + r + 1, cy + r - 3), fill=(15, 18, 25))
        draw.ellipse((cx - r, cy - r - 4, cx + r, cy + r - 4), outline=(251, 191, 36), width=3)
        draw.line((cx, cy + 2, cx, cy + 18), fill=(251, 191, 36), width=3)
        draw.line((cx, cy + 12, cx + 6, cy + 12), fill=(251, 191, 36), width=3)
        draw.line((cx, cy + 17, cx + 5, cy + 17), fill=(251, 191, 36), width=3)

    elif ch == "D":
        # Reinforced Medieval Oak Door
        draw.rectangle(box, fill=(92, 51, 23), outline=(45, 25, 12), width=1)
        draw.line((x0 + w // 3, y0, x0 + w // 3, y1), fill=(60, 34, 16), width=1)
        draw.line((x1 - w // 3, y0, x1 - w // 3, y1), fill=(60, 34, 16), width=1)
        draw.rectangle((x0 + 3, y0 + 10, x1 - 3, y0 + 16), fill=(71, 85, 105))
        draw.rectangle((x0 + 3, y1 - 18, x1 - 3, y1 - 12), fill=(71, 85, 105))
        draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=(245, 158, 11))
        draw.line((cx, cy, cx, cy + 4), fill=(15, 18, 25), width=2)

    elif ch == "G":
        # Mystical Portal Goal
        r1 = 18
        r2 = 12
        r3 = 6
        draw.ellipse((cx - r1, cy - r1, cx + r1, cy + r1), outline=(16, 185, 129), width=3)
        draw.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(6, 78, 59), outline=(110, 231, 183), width=2)
        draw.ellipse((cx - r3, cy - r3, cx + r3, cy + r3), fill=(167, 243, 208))

    elif ch == "E":
        # Crimson Horned Shadow Fiend Enemy
        r = 13
        draw.ellipse((cx - r + 1, cy + r - 3, cx + r - 1, cy + r + 3), fill=(15, 18, 25))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(220, 38, 38), outline=(153, 27, 27), width=2)
        draw.polygon([(cx - r + 2, cy - r + 2), (cx - r - 4, cy - r - 6), (cx - r + 5, cy - r - 2)], fill=(153, 27, 27))
        draw.polygon([(cx + r - 2, cy - r + 2), (cx + r + 4, cy - r - 6), (cx + r - 5, cy - r - 2)], fill=(153, 27, 27))
        draw.rectangle((cx - 7, cy - 3, cx - 3, cy), fill=(253, 224, 71))
        draw.rectangle((cx + 3, cy - 3, cx + 7, cy), fill=(253, 224, 71))

    elif ch in ("@", "W"):
        # Hero Blue Knight
        won = ch == "W"
        r = 13
        if won:
            draw.ellipse((cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4), outline=(251, 191, 36), width=2)
        # Drop shadow
        draw.ellipse((cx - r + 1, cy + r - 2, cx + r - 1, cy + r + 4), fill=(12, 15, 22))
        # Blue Armor
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(37, 99, 235), outline=(29, 78, 216), width=2)
        # Steel Helmet Visor
        draw.arc((cx - r + 1, cy - r - 1, cx + r - 1, cy + r // 2), 180, 360, fill=(148, 163, 184), width=3)
        # Cyan Glowing Visor Bar
        draw.line((cx - r + 4, cy - 1, cx + r - 4, cy - 1), fill=(56, 189, 248), width=3)
        # Golden Crest
        draw.polygon([(cx, cy - r - 5), (cx - 4, cy - r + 2), (cx + 4, cy - r + 2)], fill=(251, 191, 36))


def ascii_to_image(text, cell=CELL):
    from PIL import Image, ImageDraw

    all_lines = [l for l in text.split("\n") if l.strip()]
    grid_lines = [l for l in all_lines if not l.startswith("!!")]
    error_lines = [l for l in all_lines if l.startswith("!!")]
    error_msg = error_lines[0] if error_lines else ""

    cols = max((len(line) for line in grid_lines), default=1)
    rows = len(grid_lines)
    hud_h = 36
    err_h = 28 if error_msg else 0

    img = Image.new("RGB", (cols * cell, rows * cell + hud_h + err_h), (18, 21, 28))
    draw = ImageDraw.Draw(img)

    _draw_hud(draw, cols * cell, hud_h, grid_lines, error_msg)

    # Find player position for lighting vignette
    player_pos = None
    for y, line in enumerate(grid_lines):
        for x, ch in enumerate(line):
            box = (x * cell, y * cell + hud_h, (x + 1) * cell, (y + 1) * cell + hud_h)
            _draw_tile(draw, ch, box)
            if ch in ("@", "W"):
                player_pos = (x * cell + cell // 2, y * cell + hud_h + cell // 2)

    if error_msg:
        ey = rows * cell + hud_h
        draw.rectangle((0, ey, cols * cell, ey + err_h), fill=(185, 28, 28))
        draw.text((12, ey + 7), error_msg.replace("!!", "💥 DETECTOR BREACH:"), fill=(255, 255, 255))

    return img


def make_gif(seed, actions, path, fps=10, tail=None):
    """Render a replay GIF. Returns the path, or None if Pillow is missing."""
    if not has_pillow():
        return None
    frames = simulate(seed, actions)
    if tail and len(frames) > tail + 1:
        frames = frames[-(tail + 1):]
    if not frames:
        return None
    images = [ascii_to_image(frame) for frame in frames]
    images[-1] = images[-1].copy()
    duration = max(50, int(1000 / max(1, fps)))
    try:
        images[0].save(
            path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
            optimize=True,
        )
    except OSError:
        return None
    return path
