# RiverGuard - project notes for the AI assistant

## READ THIS FIRST (context folder)
Every new session should read these files before doing anything:
- `context/CURRENT.md` — snapshot of the current state (servers, data, bugs, numbers)
- `context/DONE.md` — everything completed so far
- `context/TODO.md` — what's next and what needs the owner's input
- `context/OWNER_ACTIONS.md` — what the owner must do by hand
- `reports/DECISIONS.md` — **the decision dictionary.** Every significant
  decision, why it was made, and what was rejected instead.

Update these files whenever significant progress is made.

## RULE: record significant decisions
Any choice that affects the numbers, the method, or the claims must be added to
`reports/DECISIONS.md` as a new numbered entry (D26, D27, ...) with:
- **Date**
- **Decision** — what we chose
- **Reason** — why
- **Rejected** — the alternatives, so they stay visible
- **Impact** — what it changes about the results

Rules for that file:
- **Append only.** Never edit an old decision to make it look better.
- If a decision changes, add a new entry that explicitly supersedes the old one.
- Flag anything that is an *assumption* rather than a measured fact. Those must
  never be presented as findings.
- Keep the unresolved list (D25) current. It is the memory of what we know is
  still inconsistent.

## What this project is
A final-year solo project that predicts how the Jamuna river
(Bangladesh) bankline moves over time, using years of satellite images, and
shows results in a web app. Goal: help people see where riverbank erosion is
likely, so communities and planners can act early.

## Where it lives (IMPORTANT)
- The project is physically stored on the external HDD:
  `/media/saad/HDD/riverguard`
- `~/Projects/riverguard` is a **symlink** (shortcut) to that folder.
- The HDD is **not** in `/etc/fstab`, so it must be mounted before working.
  If commands say "No such file or directory", check the HDD is mounted
  (`ls /media/saad/HDD`).

## How to run things (from the project root)
- Python environment lives at `.venv/` (rebuilt after the move to HDD).
  Always call it as `../.venv/bin/python` from inside `ml/`, or
  `.venv/bin/python` from the project root.
- ML pipeline (read-only data processing), in order:
  - `ml/01_prepare.py`  - raw GEE images -> clean, aligned rasters.
  - `ml/02_banklines.py` - rasters -> the river's edge (bankline) per year.
  - `ml/03_transects.py` - measures how far the bank moved between two years.
- Backend (Django API): `backend/`, run with
  `../.venv/bin/python manage.py runserver 127.0.0.1:8010`.
- Frontend (React + MapLibre): `frontend/`, run with `npm run dev`
  (port 5173, proxies `/api` to the backend).

## Owner's preferences (also set globally)
- Plain language, no jargon; explain what and why; teach the owner.
- Short answers by default; detail only when asked.
- Owner manually does: (1) Google Earth Engine exports, (2) Colab training.
- Do not commit/push to git unless the owner explicitly asks.
- Avoid code comments unless asked.

## Machine limits
- ~7.5 GB RAM, Intel 8-thread CPU, broken NVIDIA MX130 GPU.
- Keep heavy computation on Colab.
