# Evidence + victim art

## Victim (story briefing)

```
frontend/public/art/vane_hall/victim.webp
```

Shown on the Briefing “The victim” chapter (crime-scene plate of Sir Reginald).

## Evidence object plates

Story briefing, Present chips, notebook, Accuse method picker, and room Search hotspots look for:

```
frontend/public/evidence/vane_hall/<evidence_id>.webp
```

Until a file exists, the UI shows the gold line icon. Clicking a hotspot still collects the clue; art is visual only.

## Landed

| id | Name | Status |
|----|------|--------|
| `decanter` | The brandy decanter | **in** — crystal still on black |

## Later (when you search rooms)

| id | Name | Where |
|----|------|-------|
| `solicitor_letter` | Unsent letter to his solicitor | Study drawer |
| `ledger` | Partnership ledger | Study desk |
| `cyanide_jar` | Jar of potassium cyanide | Darkroom shelf |
| `cigar_ash` | Cigar ash | Darkroom floor |
| `cigar_case` | Pell’s cigar case | Billiard room mantel |
| `necklace_clasp` | Broken necklace clasp | Garden bench |
| `torn_reference` | Torn letter of reference | Servants’ corridor |
| `ashes_in_grate` | Burned papers | Study grate (dynamic) |

## Spec

- Format: **WebP** (PNG source ok; we convert). Square or 4:5 crop, ~900–1200px.
- Style: same amber/teal still-life mood as the character pack — not flat icons, not stock photos with watermarks.
- Transparent background preferred; dark vignette / black plate acceptable.
- Filename must match the `id` column exactly (`decanter.webp`, not `brandy.png`).

Drop more pngs/webps when ready and we will wire them the same way.
