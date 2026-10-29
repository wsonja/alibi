# Art generation brief — all cases

Paths the game expects once you drop files:

| Kind | Path |
|------|------|
| Portraits | `frontend/public/portraits/<pack>/<suspect_id>_{neutral,avatar}.webp` (+ optional emotion variants) |
| Victim plate | `frontend/public/art/<pack>/victim.webp` |
| Evidence | `frontend/public/evidence/<pack>/<evidence_id>.webp` |
| Room backdrops | `frontend/public/backdrops/landscape_16x9/<scene>.png` (plus ultrawide/mobile if you have them) |

`<pack>` = case id stem: `vane_hall`, `dorm_secrets`, `liner_caledonia`, `startup_pitch`.

Vane Hall is **done** (cast + rooms + all 9 evidence + victim). Below is what still needs generating.

---

## Vane Hall — evidence → room → surface (cheatsheet)

| Evidence id | Name | Room | Where in the room (current placement) |
|-------------|------|------|----------------------------------------|
| `decanter` | The brandy decanter | **Study** | Desk surface by the lamp (right side of library plate) |
| `ledger` | Partnership ledger | **Study** | Front of the desk, open |
| `solicitor_letter` | Unsent solicitor letter | **Study** | Desk drawer edge |
| `ashes_in_grate` | Burned papers | **Study** | Hearth / grate (left of the fire) — *dynamic, appears after framing* |
| `cyanide_jar` | Potassium cyanide jar | **Darkroom** | Chemical shelf / side desk (left) |
| `cigar_ash` | Cigar ash | **Darkroom** | Floor by the workbench |
| `cigar_case` | Pell’s cigar case | **Billiard Room** | Mantel / left sideboard |
| `necklace_clasp` | Broken necklace clasp | **Garden** | Ground by the bench / drive (exterior stand-in) |
| `torn_reference` | Torn letter of reference | **Servants’ Corridor** | Chair seat by the desk (bedroom stand-in) |
| — | — | **Drawing Room** | No clues |

Backdrop stand-ins today: study→`library`, darkroom/corridor→`bedroom`, billiard/drawing→`dining_room`, garden→`manor_exterior`. Ideal later: dedicated darkroom, garden terrace, billiard, corridor plates.

---

## Still to generate

### 1. Secrets on Campus (`dorm_secrets` / pack `dorm_secrets`)

**Mood:** Cornell Collegetown winter night, fluorescent/LED interiors, snow.

**Cast portraits** (neutral + avatar each):

| id | Name | Role |
|----|------|------|
| `hana` | Hana Sato-Reyes | Pre-med senior |
| `devin` | Devin Marsh | Owen’s suite-mate |
| `ray` | Ray Kowalczyk | Night attendant |

**Victim:** Owen Castellano (crime-scene / body plate for briefing).

**Backdrops (6):**

| scene id suggestion | Room |
|---------------------|------|
| `common_room` | Sagging couches, TV, whiteboard, porch door |
| `kitchen` | Shared fridge, microwave, labelled shelves |
| `stairwell` | Back stairwell, basement landing |
| `victims_room` | Owen’s suite / shared study |
| `laundry_room` | Basement washers/dryers, boiler |
| `porch` | Snowy side porch / steps |

**Evidence (10):**

| id | Room | Shot |
|----|------|------|
| `backpack` | common_room | Backpack on couch, front pocket unzipped |
| `whiteboard` | common_room | House whiteboard by the door |
| `pesto_container` | kitchen | Glass container labelled OWEN, NUT FREE, in the sink |
| `integrity_form` | victims_room | Printed academic-integrity form on desk |
| `cash_box` | victims_room | Grey cash box + ledger on shelf |
| `betting_slip` | stairwell | Folded notebook page on basement stairs |
| `epipens_snow` | porch | Two orange EpiPens in snow drift |
| `porch_prints` | porch | Footprints + cigarette butts on boards |
| `hoodie_dryer` | laundry_room | Open cold dryer, damp clothes |
| `dryer_lint` | laundry_room | Lint trap pulled crooked *(dynamic)* |

---

### 2. Death on the Caledonia (`liner_caledonia` / pack `liner_caledonia`)

**Mood:** 1927 ocean liner, first class, night, brass + mahogany + wet decks.

**Cast:**

| id | Name | Role |
|----|------|------|
| `delphine` | Mrs. Delphine Whitlock | Victim’s wife |
| `marlow` | Lt. Hugh Marlow | Second Officer |
| `calloway` | Major Rex Calloway | Fellow passenger |
| `ivy` | Ivy Pruett | Lady’s maid |
| `kell` | Miss Harriet Kell | Financial journalist |

**Victim:** Cornelius J. Whitlock.

**Backdrops (6):** `stateroom`, `smoking_room`, `promenade`, `wireless_room`, `service_corridor`, `lounge`.

**Evidence (10):**

| id | Room | Shot |
|----|------|------|
| `cane` | stateroom | Malacca cane, silver knob, in rack |
| `broken_glass` | stateroom | Whisky tumbler shards on carpet |
| `passenger_list` | stateroom | Annotated first-class list in dispatch case |
| `marked_deck` | smoking_room | Deck of cards in card-table drawer |
| `cigarette_ends` | promenade | Butts in lee of No. 7 boat |
| `kell_cable` | wireless_room | Cable carbon on operator’s spike |
| `whitlock_cable` | wireless_room | Outgoing cable carbon, signed C.W. |
| `typewriter` | lounge | Corona portable + page in writing alcove |
| `towel` | service_corridor | Hand towel caught in linen chute |
| `burnt_flimsy` | promenade | Charred paper in sand fire bucket *(dynamic)* |

---

### 3. The Pitch That Kills (`startup_pitch` / pack `startup_pitch`)

**Mood:** Modern glass startup office, storm night, cold LEDs + rain on glass.

**Cast:**

| id | Name | Role |
|----|------|------|
| `odell` | Marcus Odell | Co-founder / CTO |
| `kowalski` | Bea Kowalski | Head of Growth |
| `lindqvist` | Theo Lindqvist | Halcyon associate |
| `ferreira` | Ines Ferreira | Office manager |

**Victim:** Julian Ashby.

**Backdrops (6):** `boardroom`, `ceo_office`, `kitchen`, `server_room`, `roof_terrace`, `open_floor`.

**Evidence (11):**

| id | Room | Shot |
|----|------|------|
| `energy_can` | boardroom | Voltage Zero can at head of table |
| `caffeine_tub` | kitchen | Bag of pure caffeine powder |
| `paper_cup` | server_room | Crushed kitchen cup in rack waste bin |
| `badge_log` | open_floor | Printed door events under reception |
| `cap_table_memo` | ceo_office | Privileged memo on desk tray |
| `deleted_commit` | ceo_office | Folded git-commit printout in drawer |
| `slack_export` | open_floor | Slack printout under visitor badges |
| `hair_clip` | roof_terrace | Tortoiseshell clip on bench |
| `burner_phone` | kitchen | Prepaid phone in recycling |
| `log_wiped` | open_floor | Empty badge console *(dynamic)* |
| `shredder_strips` | ceo_office | Warm shredder bin strips *(dynamic)* |

---

## Spec (all packs)

- **Portraits:** square or 3:4, painterly/noir matching the case era; `*_neutral.webp` + `*_avatar.webp`.
- **Evidence:** transparent PNG/WebP, ~900–1200px, still-life on black or clear; filename = id.
- **Backdrops:** 1920×1080 PNG masters (plus 21:9 / 9:16 if you can). Don’t ship the tiny preview WebPs as the only plate.
- **Victim:** one crime-scene plate per case for the story briefing.
