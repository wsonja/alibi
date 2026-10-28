# Vane Hall Web Asset Pack — concept-board exports

## What is included
- 4 character **cards**: 744×1068, PNG + WebP (these still visibly show the concept board's alternate character names).
- 4 character **portrait images**: 900×1200, PNG + WebP (no name labels; painted backgrounds retained).
- 4 square **avatars**: 256×256, PNG + WebP.
- 4 **room/exterior scenes**: original scene compositions, PNG + WebP.
- 4 **16:9 desktop backgrounds**: 1920×1080, PNG + WebP.
- 4 **21:9 ultrawide backgrounds**: 2520×1080, PNG + WebP.
- 4 **9:16 phone backgrounds**: 1080×1920, PNG + WebP.
- 2 complete approved concept boards.
- `manifest.json`: path mappings and caveats.

## Important limitations
The approved concept board does **not** follow the original `BRIEF.md` names or physical descriptions. Canonical filenames are mapped from equivalent roles and should be treated as **provisional art**, not verified final canon. The character card images have the alternate names burned into pixels. Use the label-free portrait images in UI when displaying canonical names dynamically.
The generated board supplied small panel art, not full-resolution originals. Enlarged pixel dimensions do not add fine detail. Widescreen/mobile images extend the sides/background with softened, darkened copies of the original images; they are not independently painted widescreen views. No transparent-background character cutouts, six-expression series, full-body views, or sketches are included.

## Suggested use
Copy `characters/portraits` to `frontend/public/portraits/vane_hall/` and reference `/portraits/vane_hall/margaret_neutral.webp` (and `crane_neutral.webp`, `pell_neutral.webp`, `ada_neutral.webp`). Use WebP for performance, PNG for source-quality/reference assets. For scene backdrops, start with `/backdrops/landscape_16x9/library.webp`. Use CSS `background-size: cover; background-position: center;`.
