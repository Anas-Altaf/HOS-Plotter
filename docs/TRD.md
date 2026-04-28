# Technical Requirements Document — HOS Plotter

**Version:** 1.2
**Date:** 2026-04-28
**Status:** Implemented

---

## 1. Purpose

HOS Plotter is a single-page web application that helps US property-carrying truck drivers plan a trip in compliance with FMCSA Hours-of-Service (HOS) regulations under 49 CFR 395. Given a current location, pickup, dropoff, and current cycle hours used, the app produces:

1. A route map with all required stops (pickup, dropoff, fuel, mandatory breaks, daily resets, optional 34-hour restart).
2. One or more filled-out Driver's Daily Log (RODS) sheets covering the trip.

The app is a stateless calculator — no user accounts, no persistence — optimized for accuracy of HOS computation and clarity of presentation.

---

## 2. Scope

### 2.1 In Scope
- Trip planning for a single property-carrying driver.
- HOS rules: 11-hour driving limit, 14-hour on-duty window, 30-minute break, 10-hour off-duty reset, 70-hour/8-day and 60-hour/7-day cycles, optional 34-hour restart.
- Routing and geocoding via OpenRouteService (`driving-hgv` truck profile).
- US-only geocoding (`boundary.country=USA`).
- Map rendering with MapLibre GL.
- ELD daily log rendering (SVG overlay on `blank-paper-log.png`).
- Print and PDF export of log sheets.
- Coord pass-through: when the user picks an autocomplete suggestion, the resolved `(lat, lng)` is sent with the plan request, skipping a redundant geocode round-trip and guaranteeing exact location match.
- Deployment: backend on Render, frontend on Vercel.

### 2.2 Out of Scope
- User authentication, accounts, trip history persistence.
- Database (no DB; stateless).
- Multi-driver / team driving.
- Adverse driving conditions exception.
- Personal conveyance / yard moves.
- Sleeper-berth split provisions (7/3, 8/2). Engine inserts a single 10-hour off-duty reset.
- International routing.
- Real-time GPS tracking, ELD device integration.

---

## 3. Stakeholders & Users

| Role | Need |
|---|---|
| Driver / dispatcher | Plan a legal, efficient trip in under a minute. |
| Reviewer (assessment) | Verify accuracy, UI quality, code quality. |

---

## 4. Assumptions (per assessment)

- Property-carrying driver.
- 70 hours / 8 days OR 60 hours / 7 days cycle (user-selectable; default 70/8).
- No adverse driving conditions.
- Fueling required at least once every 1,000 miles.
- 1 hour for pickup, 1 hour for dropoff (both On-Duty Not Driving).
- Trip starts at "now" unless a start time is provided.

---

## 5. Functional Requirements

### 5.1 Inputs

| Field | Type | Validation | Notes |
|---|---|---|---|
| `current_location` | string (free-text address) | required, non-empty, geocodable | Autocomplete via ORS Pelias (US-only). |
| `pickup_location` | string | required, non-empty, geocodable, ≠ dropoff | |
| `dropoff_location` | string | required, non-empty, geocodable | |
| `current_coord` | `{label, lat, lng}` | optional | Pre-resolved coord from autocomplete pick. |
| `pickup_coord` | `{label, lat, lng}` | optional | |
| `dropoff_coord` | `{label, lat, lng}` | optional | |
| `current_cycle_hours` | number | 0 ≤ x ≤ cycle_max | Float, 1 decimal. |
| `cycle_type` | enum | `70_8` \| `60_7` | Default `70_8`. |
| `start_time` | ISO 8601 datetime | optional | Defaults to server `now()` UTC. |

### 5.2 Outputs

#### 5.2.1 Route
- Polyline (array of `[lng, lat]`).
- Total distance (miles), total drive minutes.
- Legs: current → pickup, pickup → dropoff (each with distance + duration).
- Waypoints: typed `current` / `pickup` / `dropoff` with label and coords.

#### 5.2.2 Stops (ordered)
| Type | Trigger | Duration | Duty Status |
|---|---|---|---|
| `pickup` | Start of leg 2 | 60 min | On-Duty Not Driving |
| `fuel` | Every 1,000 mi cumulative | 15 min | On-Duty Not Driving |
| `break_30` | After 8h cumulative driving without ≥30 min break | 30 min | Off Duty |
| `rest_10` | When `drive_remaining ≤ 0` OR `window_remaining ≤ 0` | 10 h | Off Duty |
| `restart_34` | When `cycle_used ≥ cycle_max` and trip not yet complete | 34 h | Off Duty |
| `dropoff` | End of leg 2 | 60 min | On-Duty Not Driving |

Each stop carries: `{ type, label, lat, lng, mile (cumulative), start (ISO), end (ISO), duration_min }`.

#### 5.2.3 Daily Logs
One log per calendar day in UTC between trip start and trip end.

Each log:
- `date` (YYYY-MM-DD)
- `from_location`, `to_location`
- `segments[]`: `{ status: "OFF"|"SB"|"D"|"ON", start_min, end_min }`, `start/end_min` ∈ [0, 1440]
- `totals`: hours per status (sum = 24)
- `total_miles_today`
- `remarks[]`: `{ time_min, text }`
- `recap`: `{ "70_8": { A, B, C }, "60_7": { A, B, C } }`

### 5.3 HOS Engine

Pure-Python deterministic simulator (`backend/hos/engine.py`). Fully unit-tested.

#### 5.3.1 State Variables
```
clock           : datetime
position_mi     : float
status          : "OFF" | "SB" | "D" | "ON"
cycle_used_min  : float
cycle_max_min   : 4200 (70h) | 3600 (60h)
window_remaining_min : float (resets to 14h on 10h off)
drive_remaining_min  : float (resets to 11h on 10h off)
since_break_min      : float (driving min since last ≥30 off)
miles_since_fuel     : float
events[]             : ordered audit trail
```

#### 5.3.2 Tick Loop (priority order)
1. Trip complete → exit.
2. `cycle_used >= cycle_max` AND trip not done → insert `restart_34` (34h Off). Reset `cycle_used = 0`, window/drive/break.
3. `window_remaining <= 0` OR `drive_remaining <= 0` → insert `rest_10` (10h Off). Reset window/drive/break.
4. `since_break_min >= 8h` → insert `break_30` (30 min Off). Reset break counter only.
5. `miles_since_fuel >= 1000` → insert `fuel` (15 min On-Duty). Reset fuel mileage. Counts toward cycle and window.
6. At pickup/dropoff waypoint → insert 1h On-Duty.
7. Else drive a chunk = `min(drive_remaining, window_remaining, leg_remaining, miles_to_break, miles_to_fuel)`.

#### 5.3.3 Speed Model
Per-leg speed derived from ORS leg duration: `speed = distance / duration`. Used to convert remaining-time to remaining-miles within a leg.

#### 5.3.4 Status Mapping
| Activity | Status |
|---|---|
| Driving | D |
| Pickup, dropoff, fuel | ON |
| 30-min break, 10h reset, 34h restart | OFF |
| Sleeper berth | SB — not used in v1 |

### 5.4 Log Builder

`backend/hos/log_builder.py` consumes engine events:
- Splits any segment crossing midnight into two segments at 00:00.
- Fills idle gaps with OFF.
- Merges consecutive same-status segments.
- Computes per-status totals (sum exactly 24h for every day).
- Carries remarks for non-drive events.
- Emits recap for both `70_8` and `60_7` cycles.

### 5.5 Routing Client

`backend/routing/ors_client.py`:
- `geocode(query)` → `{label, lat, lng}` via Pelias `/geocode/search`. **US-only** (`boundary.country=USA`), layers `locality,region,address,neighbourhood,county`.
- `autocomplete(query, size)` → ranked results via `/geocode/autocomplete`. US-only.
- `directions(coords)` → polyline + per-leg distance/duration via `/v2/directions/driving-hgv/geojson`.
  - Falls back to `way_points`-proportional split if `segments` array is missing.
  - Last-resort equal split if `way_points` also missing.
- API key from env `ORS_API_KEY`; never sent to client.
- All calls log endpoint, status, and latency.

---

## 6. API Contract

Base URL: `${BACKEND_URL}/api`

### 6.1 `POST /api/trip/plan`

**Request**
```json
{
  "current_location": "Dallas, TX",
  "pickup_location": "Houston, TX",
  "dropoff_location": "Atlanta, GA",
  "current_coord": {"label": "Dallas, TX, USA", "lat": 32.776, "lng": -96.797},
  "pickup_coord":  {"label": "Houston, TX, USA","lat": 29.760, "lng": -95.369},
  "dropoff_coord": {"label": "Atlanta, GA, USA","lat": 33.749, "lng": -84.388},
  "current_cycle_hours": 12.5,
  "cycle_type": "70_8",
  "start_time": "2026-04-28T08:00:00Z"
}
```

If a `*_coord` is supplied, the backend skips geocoding for that field. Otherwise it geocodes the string.

**Response 200**
```json
{
  "route": {
    "geometry": [[lng, lat], ...],
    "total_distance_mi": 1031.4,
    "total_drive_minutes": 990,
    "legs": [
      {"from": "...", "to": "...", "distance_mi": 240.0, "duration_min": 230},
      {"from": "...", "to": "...", "distance_mi": 791.4, "duration_min": 760}
    ],
    "waypoints": [
      {"label": "...", "lat": ..., "lng": ..., "type": "current"},
      {"label": "...", "lat": ..., "lng": ..., "type": "pickup"},
      {"label": "...", "lat": ..., "lng": ..., "type": "dropoff"}
    ]
  },
  "stops": [
    {"type":"pickup","label":"Pickup — ...","lat":...,"lng":...,"mile":240.0,"start":"...","end":"...","duration_min":60},
    {"type":"fuel","label":"Fuel stop — mile 1000","mile":1000,"...":"..."},
    {"type":"break_30","label":"30-minute break","...":"..."},
    {"type":"rest_10","label":"10-hour off-duty reset","...":"..."},
    {"type":"dropoff","label":"Dropoff — ...","mile":1031.4,"...":"..."}
  ],
  "logs": [{ "...": "see §5.2.3" }],
  "summary": {
    "total_distance_mi": 1031.4,
    "total_duration_min": 1500,
    "trip_start": "...",
    "trip_end": "...",
    "log_days": 2
  }
}
```

**Response Headers**
- `X-Request-Id`: short UUID for trace correlation.

**Errors**
| Code | Reason |
|---|---|
| 400 | Validation (pickup=dropoff, cycle out of range, missing field) |
| 422 | Geocoding failure (`detail: "Could not geocode '<query>'"`) |
| 502 | Routing service unavailable |
| 429 | Rate limit |

### 6.2 `GET /api/geocode/autocomplete?q=...`
Returns up to 5 ORS Pelias suggestions (US-only): `{ "results": [{ label, lat, lng }] }`.

### 6.3 `GET /api/health`
Returns `{ "status": "ok" }`.

---

## 7. Frontend

### 7.1 Pages
- `/` — Trip form (4 inputs + cycle toggle). Minimal Linear/Stripe-style layout; no marketing copy.
- `/result` — Waypoint chain headline, stat row (distance / drive time / total trip / log days), map, stops timeline, route legs, paginated daily logs with print + PDF.

### 7.2 Component Tree
```
App
├── Header (wordmark, Reference link)
├── Routes
│   ├── Home
│   │   └── TripForm
│   │       ├── LocationAutocomplete (×3, debounced, keyboard nav, coord capture)
│   │       ├── Cycle hours input
│   │       └── Cycle type toggle (segmented control)
│   └── Result
│       ├── Waypoint chain + timestamps
│       ├── Stat row (border-grid, mono numbers)
│       ├── RouteMap (MapLibre)
│       ├── StopsTimeline
│       ├── Route legs list
│       └── LogSheets
│           ├── Paginator
│           └── LogSheet (SVG)
└── Toaster
```

### 7.3 State
- Zustand store (`tripStore`): `inputs`, `result`, `loading`, `error`. `result` persisted to `sessionStorage` so refresh on `/result` keeps data.
- Form state via react-hook-form + zod schema.
- Local component state holds resolved coord per field.

### 7.4 ELD Log Sheet (Pure SVG)
- Viewbox 1100×720, fully programmatic — no bitmap background.
- Header: title, 24-hour subtitle, date (m / d / y w/ underlines + labels), "Original / Duplicate" notes.
- Trip metadata: From / To rules, Total Miles Today, Total Mileage Today, Carrier, Truck/Trailer #, Main Office, Home Terminal.
- Grid: 4 duty rows (Off / Sleeper / Driving / On-Duty) × 24 hourly columns; 15-min sub-ticks (the 30-min tick is taller).
- Hour labels: `Mid 1..11 Noon 1..11 Mid` above the grid.
- Row labels left of grid; totals column on the right (per-row + grand total).
- Status polyline drawn over grid: horizontal at the active row's y, vertical connector when status changes.
- Remarks band below grid: hour-aligned tick scale + auto-staggered caption text.
- Recap section: A/B/C boxes for both 70/8 and 60/7 cycles + 34-hour restart explanatory box.
- Print CSS: `@page { size: landscape; margin: 0.25in }`. One sheet per page. App chrome hidden via `.no-print`.
- Export PDF: dynamic import of `html2canvas` + `jsPDF`; one canvas per sheet, multi-page PDF.

### 7.5 Map
- MapLibre GL via `react-map-gl`.
- Tiles: MapTiler streets (vector) when `VITE_MAPTILER_KEY` set; fallback to OSM raster.
- Layers:
  - Route polyline (slate, double-stroke for casing).
  - Waypoint markers: A (current, slate) / B (pickup, emerald) / C (dropoff, rose), 24px circles.
  - Stop markers: small dots (16px) colored by stop type.
- Popups on stop click show label, mile, ETA, duration.
- Auto-fit bounds to route on load.

### 7.6 UI/UX Standards
- TailwindCSS + custom shadcn-style primitives.
- Palette: neutral slate base, no brand-blue accent. Semantic colors only for stop types (green/red/amber/yellow/violet/slate).
- Typography: Inter (UI), JetBrains Mono (numbers, dates, addresses).
- Spacing: 4px base, restrained whitespace; small fonts (12-13px body).
- Loading: in-input spinner on autocomplete; "Waking up server…" toast after 5s.
- Toasts via `sonner`.
- Keyboard: Tab order correct; arrow keys + Enter on autocomplete list; Esc closes.
- Accessibility: `aria-invalid` on errored inputs, focus rings on all interactive elements.
- Responsive: mobile (<640), tablet (640–1024), desktop (≥1024). Log sheets scroll horizontally on mobile.

---

## 8. Edge Cases

| Case | Handling |
|---|---|
| Pickup == dropoff | 400 error, inline form message. |
| Cycle hours > cycle_max | 400 error. |
| Cycle hours < 0 | 400 error. |
| Geocoding returns 0 results | 422 error, message names the failing field. |
| Wrong city (e.g. "Atlanta" → Atlanta, TX) | Autocomplete dropdown surfaces multiple matches; resolved coord locks selection; visual emerald dot confirms. |
| ORS routing returns no segments | Fallback to `way_points` proportional split, then equal split. |
| Trip drive < 1 min | Single log day, pickup + dropoff only. |
| Trip duration > 8 days even after restart | Engine continues; log builder emits one day per calendar date. |
| Fuel due during a break | Engine inserts whichever event is due first; both are logged. |
| Drive segment crosses midnight | Log builder splits at 00:00. |
| Cycle becomes exhausted mid-leg | Engine inserts 34h restart at current position. |
| Network failure | Toast "Could not plan trip". |
| Slow cold start (Render free tier) | "Waking up server…" toast after 5s. |

---

## 9. Non-Functional Requirements

### 9.1 Performance
- Plan endpoint p50 < 2s, p95 < 5s (excluding cold start).
- Map first paint < 1s on FE after data arrives.
- Log sheet render < 200ms per sheet.

### 9.2 Security
- ORS key, MapTiler key, Django secret all env-only.
- HTTPS enforced (Vercel + Render default).
- CORS: only Vercel domain whitelisted in prod.
- DRF throttling: 30/min/IP on `/plan`, 60/min/IP on `/geocode/autocomplete`.
- Input validation via DRF serializers; reject unknown fields.
- No PII stored.

### 9.3 Reliability
- Backend health check at `/api/health`.
- Graceful degradation: MapTiler → OSM raster fallback.
- Routing fallback (way_points → equal split) keeps endpoint functional even on partial ORS responses.

### 9.4 Observability
- Backend: structured logs, configurable text/json format via `LOG_FORMAT` env.
- Per-request UUID injected into every log line via `RequestIdFilter`; request id returned in `X-Request-Id` response header.
- ORS calls logged with endpoint + status + latency_ms (no payload, no key).
- Per-app loggers (`trips`, `routing`, `hos`, `access`); `urllib3`/`requests` suppressed to WARNING.
- Frontend: error boundary; console errors only in dev.

### 9.5 Maintainability
- Type hints on Python; TypeScript strict mode.
- Pure-Python HOS engine (no I/O) for deterministic testing.
- Pre-commit hooks (optional).

---

## 10. Testing

### 10.1 Backend

**Total: 56 tests, all passing.**

| Suite | File | Count | Focus |
|---|---|---|---|
| HOS engine | `hos/tests/test_engine.py` | 15 | short trip, pickup/dropoff durations, 30-min break trigger, 10h reset, fuel intervals, cycle exhaustion → restart, 60/7 cycle, distance preservation, status mapping, midnight grid bounds |
| Log builder | `hos/tests/test_log_builder.py` | 9 | empty input, single segment, midnight split, totals=24h invariant, remarks order, miles per drive only, recap shape, segment merging, both cycle recaps |
| ORS client | `routing/tests/test_ors_client.py` | 12 | geocode happy path, no-features, missing key, request error, autocomplete results / errors, directions parse + segment fallback + equal-split, 4xx → RoutingError, validation errors |
| Serializers | `trips/tests/test_serializers.py` | 10 | minimal valid, pickup=dropoff, cycle bounds (70/60/<0), missing field, invalid enum, default cycle, coord pass-through, invalid coord |
| Views (API) | `trips/tests/test_views.py` | 10 | health, plan happy path, validation 400, geocode 422, routing 502, coord pass-through skips geocode, response shape, request-id header, autocomplete proxy, short-query short-circuit |

Run:
```bash
cd backend
.venv/Scripts/python -m pytest -q
```

### 10.2 Frontend
- TypeScript strict build (`tsc -b`) gates every PR.
- Vite production build.

### 10.3 Manual Acceptance
- Reviewer runs assessment example trips end-to-end.
- Output passes HOS rule check.
- UI is professional and consistent.

---

## 11. Repository Layout

```
HOS-Plotter/
├── README.md
├── docs/
│   └── TRD.md                       (this file)
├── backend/
│   ├── manage.py
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── render.yaml
│   ├── .env.example
│   ├── core/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── middleware.py            (RequestId, access log)
│   ├── trips/
│   │   ├── apps.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── exceptions.py
│   │   ├── urls.py
│   │   └── tests/
│   │       ├── test_serializers.py
│   │       └── test_views.py
│   ├── hos/
│   │   ├── engine.py
│   │   ├── rules.py
│   │   ├── log_builder.py
│   │   └── tests/
│   │       ├── test_engine.py
│   │       └── test_log_builder.py
│   └── routing/
│       ├── ors_client.py
│       └── tests/
│           └── test_ors_client.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── vercel.json
    ├── .env.example
    ├── index.html
    ├── public/
    │   ├── favicon.svg
    │   └── blank-paper-log.png
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── vite-env.d.ts
        ├── pages/
        │   ├── Home.tsx
        │   └── Result.tsx
        ├── components/
        │   ├── trip-form/
        │   │   ├── TripForm.tsx
        │   │   └── LocationAutocomplete.tsx
        │   ├── route-map/RouteMap.tsx
        │   ├── stops-timeline/StopsTimeline.tsx
        │   ├── log-sheet/
        │   │   ├── LogSheet.tsx
        │   │   └── LogSheets.tsx
        │   └── ui/ (Button, Input, Label, Card)
        ├── lib/
        │   ├── api.ts
        │   ├── types.ts
        │   └── utils.ts
        ├── store/trip-store.ts
        └── styles/globals.css
```

---

## 12. Environment Variables

### Backend (Render)
| Var | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret |
| `DEBUG` | `False` in prod |
| `ALLOWED_HOSTS` | Render domain |
| `CORS_ALLOWED_ORIGINS` | Vercel domain |
| `ORS_API_KEY` | OpenRouteService |
| `ORS_BASE_URL` | (optional) override |
| `LOG_LEVEL` | DEBUG / INFO / WARNING |
| `LOG_FORMAT` | `text` (dev) / `json` (prod) |
| `DEFAULT_TIMEZONE` | fallback |

### Frontend (Vercel)
| Var | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Render BE URL |
| `VITE_MAPTILER_KEY` | (optional) MapTiler tiles |

---

## 13. Deployment

### 13.1 Backend (Render)
- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start: `gunicorn core.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 30`
- Free tier OK; expect cold start.
- Health check path: `/api/health`.
- Config: `backend/render.yaml`.

### 13.2 Frontend (Vercel)
- Framework: Vite.
- Build: `npm run build`.
- Output: `dist`.
- SPA rewrite: `frontend/vercel.json`.

### 13.3 CI (optional)
GitHub Actions: BE tests + FE build on PR.

---

## 14. Deliverables (Assessment)

- [x] GitHub mono repo (public).
- [x] Backend code + tests (56 passing).
- [x] Frontend code (typed, builds clean).
- [ ] Live frontend URL (Vercel).
- [ ] Live backend URL (Render).
- [ ] 3-5 minute Loom walkthrough (app + code).
- [x] README with setup, env vars, architecture diagram.

---

## 15. Open Questions

None. Ready for deployment.

---

## 16. Glossary

- **HOS** — Hours of Service.
- **RODS** — Record of Duty Status.
- **ELD** — Electronic Logging Device.
- **DOT** — Department of Transportation.
- **FMCSA** — Federal Motor Carrier Safety Administration.
- **ORS** — OpenRouteService.
- **HGV** — Heavy Goods Vehicle (truck routing profile).
- **34-hr restart** — ≥34 consecutive hours off-duty resetting the 60/70-hour cycle.
- **Pelias** — Open-source geocoder; ORS uses it for `/geocode/*`.
- **MapLibre GL** — Open-source WebGL map renderer (Mapbox GL fork).

---

## 17. Changelog

### v1.2 — 2026-04-28
- Replaced PNG-overlay log sheet with **pure SVG** renderer. Single 1100×720 viewBox, fully programmatic grid + ticks + status polyline + recap boxes. Pixel-perfect at any zoom; print-clean; no bitmap dependency.
- Recap cells widened to 140×108 with two-line wrapped subtitles (`<tspan>`).
- 34-hour restart note rendered as multi-line tspan block.

### v1.1 — 2026-04-28
- US-only geocoding (`boundary.country=USA`) — fixes ambiguous city resolution.
- Coord pass-through API: skip redundant geocoding when frontend supplies resolved coords.
- Routing fallback: when ORS returns no `segments`, derive legs from `way_points` proportionally; last-resort equal split.
- Structured logging with per-request `X-Request-Id`, named app loggers, ORS call latency tracking.
- UI overhaul to restrained Linear/Stripe-style: removed marketing hero, neutral palette, compact stat row, segmented control for cycle, in-input loading/resolved indicators, cycle-near-limit hint.
- Test suite expanded from 15 → 56 (engine, log builder, ORS client, serializers, views/API).

### v1.0 — initial
- Django + DRF backend, no DB.
- HOS engine + log builder + ORS client.
- React + Vite + Tailwind + MapLibre frontend.
- Trip form, result page, log sheet SVG with print + PDF.
