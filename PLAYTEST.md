# Playtest guide (contains Vane Hall spoilers)

## 1. Install (once)

You need git, Python 3.11+ and Node 20+.

```bash
git clone https://github.com/wsonja/alibi.git
cd alibi
make setup
```

No `make` (Windows without WSL)? Run the equivalent by hand:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt      # Windows: backend\.venv\Scripts\pip install -r backend\requirements.txt
cd frontend && npm install && cd ..
cp backend/.env.example backend/.env
```

Optional: for live AI suspects, put a Gemini key (free at aistudio.google.com) in `backend/.env` as
`GEMINI_API_KEY=...`. Without it the suspects are scripted and still fully playable.

## 2. Run (two terminals)

```bash
make backend      # API on http://localhost:8000   (manual: cd backend && .venv/bin/uvicorn --app-dir ../scripts mock_api:app --port 8000)
```

```bash
make frontend     # game on http://localhost:5173  (manual: cd frontend && npm run dev)
```

Open http://localhost:5173. If a screen shows "The lamp went out", reload the page.

## 3. Play Vane Hall (the guided route)

1. Setup screen: leave **Manor 1923** selected, difficulty Detective, press **Begin**.
2. Briefing: read it, hover the suspect cards for their public alibis, press **Begin Investigation**.
3. Click **Thomas Pell**, tab **ASK**, type: `Where were you at twenty past eleven?` He lies about fetching cigars.
4. Click **The Billiard Room** in Locations, tab **SEARCH**, press Search. You find his cigar case (it was on the
   mantelpiece all evening, so he never needed to fetch cigars).
5. With Pell selected, tab **PRESENT**, pick **Mr. Pell's cigar case**, press Present. Watch his pressure bar jump and
   his emotion change. Now ASK him: `So you never went to your room. Where did you really go?` He should admit he went
   to the study.
6. Click **Ada Finch**, tab **TACTIC**, press **Flatter** twice (text optional). Kindness works on her. Then ASK:
   `What did you see outside the study at twenty past eleven?` With enough pressure she tells you she saw Pell leave the
   study pulling off gloves.
7. SEARCH **The Darkroom** (cyanide jar with the level below the mark, fresh cigar ash) and **The Study** (the ledger
   and an unsent letter to the solicitor about the Manchester accounts). Tip: search the Study before turn 10 or Pell
   may burn the letter.
8. Optional: PRESENT the ledger or the letter to Pell, then the cyanide jar. Try **CONFRONT** with Pell and Ada
   selected (select Ada, then the ⚔ button on Pell) on the topic `the gloves`.
9. Press **ACCUSE**: suspect Thomas Pell; method evidence the brandy decanter and the cyanide jar; motive
   `embezzlement from the Manchester accounts, Reginald was going to dissolve the partnership and go to the police`;
   confidence Certain; ACCUSE.
10. Case Closed: check the verdict, score, rank, the truth panel and the reveal reel (what each suspect said vs. what
    they were privately thinking).

Things to try to break it: threaten Ada (she shuts down for two turns), use Silence on Margaret, ask Dr. Crane about the
telephone call he never made, accuse the wrong person, play the Startup Office or Cornell Dorm cases.

## 4. Report bugs

Note the screen, what you clicked, and any red text in the browser console (F12 → Console). Games are in memory only,
so restarting `make backend` wipes them.
