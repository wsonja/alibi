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

Transparent RGBA plates preferred (black/dark UI falls behind them). Handwritten dates/text on letter/ledger art are illustrative — canonical wording stays in case JSON / UI copy.

Source pack (png + lossless webp + contact sheet + id map): `docs/art-direction/vane_hall/evidence_source/`.

## Landed

| id | Name | File |
|----|------|------|
| `decanter` | The brandy decanter | `decanter.webp` |
| `solicitor_letter` | Unsent letter to his solicitor | `solicitor_letter.webp` |
| `ledger` | Partnership ledger | `ledger.webp` |
| `cyanide_jar` | Jar of potassium cyanide | `cyanide_jar.webp` |
| `cigar_ash` | Cigar ash | `cigar_ash.webp` |
| `cigar_case` | Pell’s cigar case | `cigar_case.webp` |
| `necklace_clasp` | Broken necklace clasp | `necklace_clasp.webp` |
| `torn_reference` | Torn letter of reference | `torn_reference.webp` |

## Still open

| id | Name | Notes |
|----|------|-------|
| `ashes_in_grate` | Burned papers | Dynamic clue — no plate yet |

## Spec

- Format: **WebP** (PNG source ok). Transparent background preferred.
- Filename must match the `id` column exactly (`decanter.webp`, not `brandy.png`).
