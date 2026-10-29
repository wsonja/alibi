# Vane Hall backdrops (runtime)

| Folder | Use |
|--------|-----|
| `landscape_16x9/` | Default desktop — **`.png` source** (1920×1080) plus a high-quality `.webp` |
| `ultrawide_21x9/` | Wide aspect (≥ 2:1) — high-quality `.webp` from pack PNG |
| `mobile_9x16/` | Portrait phones — high-quality `.webp` from pack PNG |
| `scene_originals/` | Thumbs / previews |

Scenes: `manor_exterior`, `library`, `dining_room`, `bedroom`.
Mapped from case rooms in `frontend/src/lib/backdrops.ts`.

The first install used the pack’s tiny preview WebPs (~100KB). Runtime landscape now prefers the PNG masters from the same zip.
