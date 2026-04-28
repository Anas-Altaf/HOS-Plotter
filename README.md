# HOS Plotter

A full-stack trip planner for US property-carrying truck drivers. Enter the current location, pickup, and dropoff plus current cycle hours; the app produces a route map with all required stops (fuel, 30-min breaks, 10-hr resets, 34-hr restart) and renders filled-out Driver's Daily Log sheets.

**Stack:** Django 5 + DRF (backend) · React 18 + Vite + TypeScript + Tailwind + MapLibre GL (frontend) · OpenRouteService (truck routing + geocoding).

> Compliance reference: 49 CFR 395.3 — Property-carrying driver. 11/14/30-min/10/70-8/60-7/34-restart. Adverse conditions and personal conveyance are out of scope.

---

## Repository layout

```
HOS-Plotter/
├── backend/        Django + DRF API
├── frontend/       Vite + React + TS app
├── docs/
│   └── TRD.md     Technical Requirements Document
└── blank-paper-log.png  Driver's Daily Log template (used by SVG renderer)
```

---

## Quick start (local dev)

### Prerequisites
- Python 3.12
- Node 18+
- An OpenRouteService API key (free): https://openrouteservice.org/dev/#/signup
- Optional: a MapTiler API key for nicer map tiles (free): https://www.maptiler.com/

### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env: paste ORS_API_KEY=<your key>

python manage.py runserver 0.0.0.0:8000
```

Health check: <http://localhost:8000/api/health>

### 2. Frontend
```bash
cd frontend
npm install
cp .env.example .env
# Edit .env if backend URL differs from default
# VITE_API_BASE_URL=http://localhost:8000
# VITE_MAPTILER_KEY=<optional>

npm run dev
```

Open <http://localhost:5173>.

---

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

15 HOS engine + log builder tests cover: short trip, break trigger, 10h reset, fuel intervals, cycle exhaustion, restart, multi-day splitting, totals correctness.

---

## API

### `POST /api/trip/plan`
**Request**
```json
{
  "current_location": "Dallas, TX",
  "pickup_location": "Houston, TX",
  "dropoff_location": "Atlanta, GA",
  "current_cycle_hours": 12.5,
  "cycle_type": "70_8"
}
```

**Response** — full geometry, ordered stops, per-day logs, summary. See [docs/TRD.md §6](docs/TRD.md) for the full schema.

### `GET /api/geocode/autocomplete?q=...`
Returns up to 5 ORS Pelias suggestions.

### `GET /api/health`
`{ "status": "ok" }`

---

## HOS engine

`backend/hos/engine.py` is a deterministic, pure-Python simulator. No I/O. Fully unit-testable.

Tick-loop priority:

1. Trip complete → exit
2. `cycle_used >= cycle_max` → 34-hour restart
3. `window_remaining <= 0` OR `drive_remaining <= 0` → 10-hour off-duty reset
4. `since_break >= 8h` driving → 30-minute break
5. `miles_since_fuel >= 1000` → 15-minute fuel stop
6. At pickup/dropoff waypoint → 1-hour on-duty
7. Else drive a chunk capped by all remaining timers

`backend/hos/log_builder.py` slices the resulting events at midnight boundaries, fills idle time as Off-Duty, computes per-status totals, and emits one log per calendar day.

---

## ELD log rendering

The provided `blank-paper-log.png` is used as the visual background of an SVG component (`frontend/src/components/log-sheet/LogSheet.tsx`). On top, we draw:

- Status line (Off / Sleeper / Driving / On-Duty rows) as a polyline
- Header date (m/d/y), From / To
- Per-row totals + grand total in the right-hand column
- Remarks (vertical ticks at event times, captioned below the grid)
- Recap A/B/C boxes for both 70/8 and 60/7 cycles
- Total miles today and footer fields

Print CSS lays out one sheet per landscape page. PDF export uses `html2canvas` + `jsPDF`.

---

## Deployment

### Backend → Render
- Connect the GitHub repo, root directory `backend`, runtime Python.
- Settings come from `backend/render.yaml`. Set `ORS_API_KEY` and `CORS_ALLOWED_ORIGINS` in the Render dashboard.

### Frontend → Vercel
- Import the GitHub repo, set the root to `frontend`, framework preset Vite.
- Environment variables:
  - `VITE_API_BASE_URL` = your Render backend URL
  - `VITE_MAPTILER_KEY` = optional, for vector tiles

`frontend/vercel.json` adds an SPA rewrite.

---

## Documentation

- [Technical Requirements Document](docs/TRD.md) — full spec.

---

## Out of scope (v1)

- Authentication, accounts, trip history persistence
- Database (stateless API)
- Sleeper-berth split provisions (7/3, 8/2)
- Adverse driving conditions exception
- Personal conveyance / yard moves
- Real-time GPS / ELD device integration

---

## License

Built for the Spotter Full Stack Developer assessment.
