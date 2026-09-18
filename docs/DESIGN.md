# DESIGN.md — Visual spec for "Murder Mystery Mayhem"

This transcribes the reference mockups the owner supplied (you cannot see them; this document is the source of truth).
The game engine/repo is "Alibi" (PLAN.md); the on-screen brand is **MURDER MYSTERY MAYHEM**.

## 1. Mood and materials

A 1920s private study / library at night, rendered like a warm pixel-art / painted adventure game.
Every screen sits on the same **room backdrop**: dark mahogany wall panelling, bookshelves, red velvet curtains,
brass wall lamps with warm glow, a fireplace, framed portraits. Foreground: a polished wooden desk with stacks of
leather books (spines read INTERROGATE / OBSERVE / CONNECT / SOLVE), a black mug ("GOOD SUSPECTS MAKE GREAT STORIES"),
a folded newspaper ("A FRESH CASE AWAITS..."), a magnifying glass, a fountain pen, a stamped folder "CONFIDENTIAL".
We cannot ship illustrations, so the backdrop is built from CSS: layered gradients (wood grain, vignette, lamp glow),
a subtle repeating pattern for panelling, and a few CSS/SVG props (book stack, mug, folder) are optional garnish.
Do NOT load external images. Inline SVG and CSS only. Fonts from Google Fonts are allowed.

UI panels are physical objects on the desk:
- **Parchment cards** — cream paper (#F3E7CB → #EADBB4 gradient), a double border: outer 3px #7A4B22 (dark wood),
  inner 1px #C9A24B (gold) inset by 5px, small corner flourishes (◆ or a tiny SVG ornament), soft drop shadow.
- **Lacquer panels** — near-black (#15100C / #1B1410) with a 2px gold border (#C9A24B) and an inner 1px #5A3A1A line.
  Used for dialogue logs, ticker, debug/judge overlay, evidence tray.
- **Wall placards** — small dark brass-framed plaques with gold serif caps: "PEOPLE LIE. DETAILS DON'T.",
  "SAME ROOF. DIFFERENT TRUTHS.", "A FRESH CASE. A FULL HOUSE. THE TRUTH WAITS.", "MYSTERIES FOR EVERY MIND.",
  "MORE PEOPLE. MORE POSSIBILITIES.", "TRUTH LIVES IN THE DETAILS.", "SAME CRIMES. DEEPER SECRETS.",
  "NEW PEOPLE. NEW LIES. EVERY TIME." (the brand tagline).
- **Sticky notes** — pale yellow (#F5E6A3) rotated 2–4°, handwritten font, a red push-pin dot.
- **Section headers** — serif small caps, centred, flanked by ornamental rules: `—◆— THE SUSPECTS —◆—`,
  with a tiny grey subtitle in caps on the right: "FOUR PEOPLE. FOUR VERSIONS."

## 2. Palette (CSS custom properties, define on :root)

```
--wood-900:#1A0F0A  --wood-800:#2A1610  --wood-700:#3B2116  --wood-600:#5A331C  --wood-500:#7A4B22
--gold-500:#C9A24B  --gold-400:#E0BC63  --gold-300:#F0D48A  --gold-glow:rgba(240,200,110,.35)
--red-700:#7E1414   --red-600:#9C1C1C  --red-500:#B92626   --marquee:#D8232A
--paper-100:#F6EBD2 --paper-200:#F3E7CB --paper-300:#EADBB4 --paper-400:#D9C596 --ink:#2B1B12 --ink-soft:#5B4636
--lacquer:#15100C   --lacquer-2:#1B1410 --lacquer-3:#231A14
--truth:#3FA34D  --deflect:#E0A422  --lie:#D23B3B  --rumor:#8A8F98
--emotion-neutral:#6B7280 --emotion-nervous:#D97706 --emotion-angry:#DC2626 --emotion-smug:#7C3AED
--emotion-sad:#2563EB --emotion-afraid:#0D9488
```
Text on parchment is --ink; text on lacquer is --paper-200 with gold accents. Never pure white.

## 3. Type

- Display / logo: **"Cinzel Decorative"** (weights 700, 900) — the marquee "MURDER MYSTERY MAYHEM".
- Headings, buttons, placards: **"Cinzel"** 600/700, letter-spacing .08em, uppercase.
- Body on parchment: **"IM Fell English"** (or "EB Garamond" fallback) 17–18px, line-height 1.5.
- Handwriting (notebook, stickies): **"Caveat"** 20–22px.
- Dialogue log / debug: **"IBM Plex Mono"** 13–14px.
- Load via one `<link>` in index.html; give every family a real fallback stack.

## 4. The marquee logo

Top-centre on every screen (smaller on Investigation). "MURDER MYSTERY" on line 1, "MAYHEM" larger on line 2, fill
--marquee red with a gold outline (`-webkit-text-stroke` or layered text-shadow) and a warm glow; a row of tiny
gold "bulb" dots along the top and bottom edges (CSS radial-gradient repeating background on a pseudo-element).
A magnifying-glass SVG overlaps the right end. Under it: "NEW PEOPLE. NEW LIES. EVERY TIME." in gold Cinzel 11px.
On Investigation the logo shrinks to a 140px-wide badge at top-left.

## 5. Screens

### 5.1 Setup — New Case  (route `/`)
Central parchment card titled `—◆— SETUP — NEW CASE —◆—`. Rows:
1. **Where does this happen?** (subtitle right: "A NEW SCENE. A FRESH SET OF SECRETS.") — five landscape tiles
   (~180×110): *Manor 1923*, *Ocean liner*, *Startup office*, *Cornell dorm*, *Your room 📷*. Selected tile has a
   thick gold border and glow. Tiles are CSS-illustrated scenes (gradients + a silhouette SVG: a manor, a ship,
   an office window, a dorm building, a bedroom lamp). Tiles map to available cases; a tile whose case is not
   installed shows a small "NEEDS API KEY" ribbon when LLM mode is scripted (procedural generation requires Claude).
2. **How many suspects?** (subtitle "MORE PEOPLE. MORE POSSIBILITIES.") — chips 3 / 4 / 5 (selected: gold).
3. **Difficulty** (subtitle "SAME CRIMES. DEEPER SECRETS.") — Rookie / Detective / Inspector.
4. **Accessibility options** (subtitle "MYSTERIES FOR EVERY MIND.") — four toggle pills with icons:
   🎤 Voice play, 🖥 Screen reader, 🍃 Low-sensory, Aa Dyslexia text.
5. 📷 checkbox: **"Suspects will read your expression. Video never leaves your device."** (subtitle "YOUR FACE. A NEW CLUE.")
6. Big red lacquer button `✦ GENERATE CASE ✦` (label becomes `✦ BEGIN: <case title> ✦` when a hand-written case is
   selected). Below it a lacquer strip with a typewriter icon and progress text:
   "Writing the cast… planting the evidence… checking it's solvable…" and a gold progress bar (shown while generating
   or while the game is being created).
A small "Case Archive" link (top-right placard) goes to `/archive`. A subtle "Suspects: Live Claude / Scripted"
status pill in the footer; clicking it opens a small modal to paste an Anthropic API key (stored only in backend/.env).
Left of the card: a CSS/SVG pixel-detective silhouette (fedora, trench coat) is a nice-to-have, not required.

### 5.2 Briefing — The Crime  (route `/game/:id/briefing`)
Large parchment card, header `—◆— BRIEFING — THE CRIME —◆—` with "SAME ROOF. DIFFERENT TRUTHS." at right.
- Left 55%: **✜ WHAT HAPPENED?** narrative paragraphs (the case `briefing`), then two small dark panels side by side:
  **TIME OF DEATH** (a clock face SVG + "Between HH:MM – HH:MM" derived from the public timeline / cause-of-death text)
  and **CRIME SCENE: <location>** (a CSS scene thumbnail + "📍 View location").
- Right 45%: **THE SUSPECTS** — "N PEOPLE. N VERSIONS." — 2×2 grid of suspect cards: pixel portrait (96px), NAME in
  caps, role in italics, `public_description` in small type, a 🔍 button. Hovering/focusing a card shows a dark speech
  bubble "ALIBI (PUBLIC)" quoting the stated alibi (from `public_description`).
- Bottom strip: **INITIAL EVIDENCE — A FEW CLUES TO GET YOU STARTED.** horizontal row of evidence cards (dark, with a
  simple icon per evidence type and the name) with ◀ ▶ arrows if overflowing.
- Public timeline as a thin vertical list under the narrative (time badge + event).
- Red button `BEGIN INVESTIGATION ▸` full width at the bottom.

### 5.3 Investigation  (route `/game/:id`)
Three columns on desktop (20% / 55% / 25%); stack on mobile with THE ROOM first.
Header centre: `INVESTIGATION` in gold Cinzel with subtitle "QUESTION • EXPLORE • CONNECT • UNCOVER".
**Left — SUSPECTS n/n** (lacquer list): one card per suspect: 56px portrait, name, a `Pressure` bar (10 segments,
green→amber→red as stress_pct rises; the label must say Pressure, not stress), "📍 <last seen>". Selected card:
gold border + glow. Shift-click (or a small "⚔" button) selects a second suspect for confrontation (both highlighted,
second in red). Below: **LOCATIONS** list with a search field; clicking a location selects it for the Search tab.
Bottom: an analog clock SVG + time text ("12:15 AM · Night") and **RECENT EVENTS** ticker line (fades in; no
animation in low-sensory mode).
**Centre — THE ROOM**: a scene panel (room gradient + lamp glow) with the selected suspect's large pixel portrait
(160–200px, emotion variant) and name plate; on the right a floating italic quote bubble with the suspect's `tell`
(physical detail) — e.g. "her hand goes to her throat and finds no necklace there". Under the portrait a parchment
speech panel with the latest spoken line. Under that, the **dialogue log** (lacquer, mono font): rows
"You:" / "<Name>:" with the clock time at right; auto-scrolls; suspect names coloured by suspect (4 accent colours).
While a reply is pending the portrait dims and the suspect's nervous tell shows in italics ("…twists her apron").
**Action bar** (below the log, never covering the portrait): five tabs — 💬 ASK "Ask a question" · 📄 PRESENT
"Show evidence" · 🎭 TACTIC "Change approach" · ❗ CONFRONT "Challenge a lie" · 🔍 SEARCH "Explore a room".
Under the tabs: the tab body (text input + mic button; evidence picker chips; four tactic buttons Bluff/Flatter/
Threaten/Silence + optional text; confront topic + rounds + "Just watch" toggle; location picker) and one red
`SEND` button (label changes: SEND / PRESENT / USE TACTIC / START CONFRONTATION / SEARCH).
Keyboard: 1–5 switch tabs, Enter sends, Esc cancels, ` toggles the Judge panel, A opens Accuse.
**Right — COMPOSURE** (meter card: segmented bar + label Calm/Neutral/Nervous + "Staying composed reveals more.";
shows "Camera off" when sensors are off) and **DETECTIVE'S NOTEBOOK** (parchment) with tabs Notes · Alibi Board ·
Evidence · Graph. Notes: per-suspect bullets from Watson's notebook plus "Working Notes" (suggested_next) and a
handwritten sticky. Alibi Board: rows per suspect, columns = time slots; claim chips; overlapping/contradicting
claims outlined amber/red. Evidence: examined items with detail (magnifier), unexamined greyed. Graph: React Flow
relationship/rumor graph (public info only: who accused whom in what you witnessed).
Bottom-right: red button `⚖ ACCUSE — Present your final conclusion`.

### 5.4 Confrontation view (inside Investigation when a confrontation runs)
The Room switches to two portraits facing each other with a gold lightning-bolt `VS` between them, a spotlight
cone from above. Each portrait has a speech bubble with its latest line, names coloured (A red, B blue). Under
them a lacquer log of the exchange with mini portraits; a "…" typing indicator on the speaker currently
generating. Buttons: red `💬 INTERJECT — Ask a question. Change the tide.` (opens a one-line input; sent before the
next round) and black `👁 JUST WATCH — Let them dig deeper.`; an `AUTO PROCEED` toggle. Left column card shows the
selected suspect's Motive/Alibi/Known-for notes (from public description) and a `RELATIONSHIP: TENSE/WARM/…` bar
derived from what the player has seen (accusations between them).

### 5.5 Accuse modal
Red banner `☞ ✦ ACCUSE ✦ — IT ALL COMES DOWN TO THIS` over a parchment sheet with three columns:
**1. THE SUSPECT — Who did it?** portrait grid (selected gold) · **2. THE METHOD — How did they do it?** list of
examined evidence (icon, name, one-line detail), multi-select · **3. THE MOTIVE — Why did they do it?** radio list
Inheritance / Revenge / Blackmail / Jealousy / Financial trouble / Other… with a free-text "Type your theory…"
(the free text is what gets sent as `motive_text`, prefixed by the chosen category).
**4. HOW SURE ARE YOU?** red slider with ticks Not sure · A hunch · Pretty sure · Certain.
Warning line `⚠ This ends the investigation. ⚠`. Buttons red `☞ ACCUSE` / black `NOT YET`.
Sticky note: "Once you accuse, the story moves forward. Are you ready?"

### 5.6 Case Closed — Debrief  (route `/game/:id/debrief`)
Header banner `CASE CLOSED` (gold on red) + verdict strip `CORRECT! YOU FOUND THE TRUTH.` or
`WRONG. THE TRUTH WAS ELSEWHERE.` + rank + confidence badge. A quote placard "SAME PEOPLE. DIFFERENT TRUTHS."
**THE TRUTH COMES TO LIGHT** (the Reveal Reel): a grid, rows = suspects (portrait, name, role), columns = the turns
in which they spoke (chunked; horizontally scrollable). Each cell: the spoken line in a chip coloured by honesty
(truthful green, evasive amber, lie red) and beneath it a 🔍 line with the private `internal_reasoning`
(collapsed by default; "Expand all" toggle). A shield icon marks lines where the Leak Guard intervened. A scrubber
slider moves a highlighted column across all rows. Legend: ● Truth ● Deflection ● Lie.
Below, three panels: **RUMOR MAP — HOW THE STORY SPREAD** (React Flow: portraits as nodes, animated edges per
off-screen message/confrontation accusation, edge colour by channel; text on hover); **WHAT YOU MISSED — CLUES THAT
COULD HAVE HELPED** (list: icon, name, one line, badge MISSED / NEAR); **CASE STATS** (Turns used, Evidence found %
bar, Tactics used, Composure average, and a quote "Facts solve cases. But people make them interesting.").
Buttons row: `◀◀ REWIND TO TURN n — See what you missed.` · `↻ RETRY SAME CASE — You know more now.` ·
`👥 NEW CASE, SAME CAST — Different crime. New lies.` (disabled in scripted mode with tooltip) ·
`⤴ SHARE CASE SEED — Let others solve it.` (copies the case export JSON URL) · `Export reel (JSON)`.
Also the truth narrated: murderer, method, motive, the true timeline, and the red herrings, in a parchment panel.

### 5.7 Judge / Debug overlay (toggle with ` or F9; only when /debug returns 200)
Full-screen dark overlay. Header `⚙ JUDGE / DEBUG — DEMO & DEVELOPMENT ONLY · NOT FOR PLAYERS`, a `F9 Toggle
Debug Overlay` key-cap badge, an X. One column per suspect (teal-on-black panels, gold border):
portrait, **Live Pressure** bar with number and the three thresholds as ticks, **Secrets** list (tier, id,
🔒 locked / 🔓 unlocked / 💬 revealed), **heard[] (n)** as a mono list with provenance "(turn 3, from ada, private)",
**outbox** list, **Private state** dots: emotion, last honesty, last internal_reasoning (mono, wrapped),
guard events count. Bottom row: **INVESTIGATION STATE** (case, difficulty, turn, clock, evidence examined n/m,
selected suspect), **EVENT LOG (MOST RECENT)** mono (guardrail + world events), **PRESSURE OVERVIEW** bar chart.
A second tab **CONTEXT BOXES**: the exact system blocks sent to each suspect on their last turn, side by side in
mono; any other suspect's secret id or secret text appearing inside a box is highlighted red (there should be none;
show a green "No cross-contamination detected" badge when clean). Make it look deliberate, not a debug dump.

### 5.8 Campaign / Case Archive  (route `/archive`)
Header `CAMPAIGN / CASE ARCHIVE — NEW PEOPLE. NEW LIES. EVERY TIME.` Top: **CAMPAIGN PROGRESSION** — a red thread
connecting round medallions for the installed cases (✓ solved, ● in progress, 🔒 not yet played). Grid of case
cards (push-pin, "Case n", title, CSS scene thumbnail, badge SOLVED / IN PROGRESS / NEW, date of last play,
difficulty chip, mini portraits). Right: detail panel for the selected case (title, tagline, description, location,
difficulty, `CONTINUE CASE` / `NEW GAME` button, KEY SUSPECTS, "PREVIOUSLY SEEN" when a suspect name recurs).
Bottom: **RECURRING SUSPECTS** (portraits with counts) and **CARRIED-FORWARD GRUDGES** (from campaign cast memory:
"Still blames you for the accusation at the Manor" arrows). Past games list with links to their debriefs.

## 6. Portraits (procedural pixel art)
No image assets. `PixelPortrait` renders a 24×28-cell pixel face into a `<canvas>` or inline SVG rects, deterministic
from a seed (suspect id) and traits parsed from `portrait_prompt` keywords:
- hair colour: dark/black, brown, grey/"grey at the temples"/"silver", blonde/fair, red/auburn; "brilliantined" =
  slicked; "pinned up" = bun; "cap" or "housemaid" = white cap; "fedora"/"hat" = hat; "spectacles"/"glasses";
  "moustache"/"mustache", "beard"; "pearl" = pearl earrings/necklace; "cigar"; "military"/"uniform" = khaki collar;
  "dinner jacket"/"evening dress"/"apron"/"tweed"/"waistcoat" choose clothing colour.
- Skin tone from words (fair/pale/olive/brown/dark) else a warm default; age words (twenties, fifty, forties) adjust
  lines/grey.
Six expression variants keyed by emotion: neutral, nervous (raised brows, a sweat drop, eyes glancing aside),
angry (V brows, tight mouth, red cheek tint), smug (one brow up, smirk, half-lidded eye), sad (down brows, mouth
down), afraid (wide eyes, open mouth, pale). Render with `image-rendering: pixelated`. Background disc tinted by
emotion colour. Blink every few seconds (skip in low-sensory). Sizes: 48, 56, 96, 160, 200.

## 7. Motion and feel
- Buttons: gold text on red lacquer, 2px gold border, subtle bevel (inset highlight), hover brightens + lifts 1px,
  active presses. Secondary: black lacquer, gold text. Disabled: desaturated.
- Panels fade/slide in 200ms. Dialogue lines type in (skip in low-sensory / reduced motion).
- The clock's hour hand moves; when clock ≥ 05:00 the time text turns red ("dawn is close") unless low-sensory.
- Toasts in the bottom-centre lacquer strip for ticker/world events.
- Everything must remain usable at 1024px wide and readable at 375px (stacked).

## 8. Accessibility
- All controls are real buttons/inputs with labels; focus rings gold; `aria-live="polite"` region receives every
  dialogue line and event. Dyslexia mode: swap body font to "OpenDyslexic" if present else "Atkinson Hyperlegible"
  (Google Fonts), letter-spacing .05em, line-height 1.7, cream-on-charcoal panels. Low-sensory: no heartbeat, no
  ticker animation, no typing effect, no clock urgency colour. Screen-reader mode: verbose labels, portraits get alt
  text "Portrait of <name>, looking <emotion>".
