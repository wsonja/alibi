# Evidence + victim art

## Victim (story briefing)

```
frontend/public/art/vane_hall/victim.webp
```

Shown on the Briefing “The victim” chapter (crime-scene plate of Sir Reginald).

## Evidence object plates

```
frontend/public/evidence/vane_hall/<evidence_id>.webp
```

Transparent RGBA preferred. Filename must match the evidence `id` exactly.

Source pack: `docs/art-direction/vane_hall/evidence_source/`.

## Landed (all 9)

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
| `ashes_in_grate` | Burned papers in the study grate | `ashes_in_grate.webp` |

## Room placement (runtime)

See `frontend/src/components/room/RoomExplore.tsx` → `SPOT_PLACEMENT`, and the art brief canvas / `docs/art-direction/ART_BRIEF.md`.
