# Evidence object art (optional next drop)

The story briefing looks for painted object plates here:

```
frontend/public/evidence/vane_hall/<evidence_id>.webp
```

Until a file exists, the UI shows the gold line icon for that object.

## First beat (already on screen)

| id | Name | Where | Suggested shot |
|----|------|-------|----------------|
| `decanter` | The brandy decanter | Study desk | Crystal decanter + one used glass, warm lamplight, noir still life |

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
- Transparent background preferred; dark vignette acceptable.
- Filename must match the `id` column exactly (`decanter.webp`, not `brandy.png`).

Drop a zip of webps (or pngs) when ready and we will wire them the same way as portraits.
