# NERIS — Product Requirements

## Original Problem
North Eastern Region Intelligence System (SIH26002). This iteration: white/institutional UI, beautiful login for Logistics Client and Government roles.

## Personas
- Government (Admin/Officer/District)
- Logistics Operator (fleet ops)
- Field Officer (mobile reporting)
- Public User (read-only)

## Iteration 7 (DONE — 2026-02) — Real routing + WebSocket push
- OSRM (public demo server, real OpenStreetMap road network) for route geometry/distance/ETA; corridor statuses overlaid by proximity; demo graph kept as offline fallback
- Route auto-fit bounds, Google-blue MAIN line + status overlays
- WS push at /api/ws?token= — broadcasts: ROAD_STATUS_CHANGED, INCIDENT_*, EMERGENCY_*, NOTIFICATION, FIELD_REPORT, PUBLIC_REPORT, VEHICLE_ADDED; targeted REROUTE_REQUIRED to drivers
- Trips API (start/list/end); blocking a road mid-trip pushes instant reroute to affected drivers

## Iteration 8 (DONE — 2026-02) — Driver merged into logistics + trips monitoring + AI auto-block
- Driver login removed; DRIVER role uses Logistics tab → /logistics (trips section merged); /driver redirects
- GET /api/trips/summary (gov+field only): live trip positions (progress along polyline), per-corridor vehicle counts; vehicles layer + trip markers gated to gov/field on maps
- AI escalation pipeline: corridor hazard ≥75% → PENDING escalation + 5-min countdown notification to gov/field; Acknowledge (MONITOR) cancels; Block now; unanswered → road auto-BLOCKED + audit + driver reroutes

## Iteration 5 (DONE — 2026-02) — Roles, verification pipeline, emergencies, environment overlays
- Pages: LogisticsWorkspace, FieldReporting (offline queue), PublicAdvisories, GisMap, Incidents, Supply, Predictions (table + map), Alerts, Audit — all live, no stubs
- Public reports → PENDING → gov/field verify or reject → verified items broadcast to all; alerts feed is role-aware
- Gov: Declare/End emergency zones (radius circles on all maps, banner, audit), broadcast notifications
- Environment overlays: live rain cells (dynamic intensity/radius) + landslide watch triangles on maps; WEATHER/HAZARD kinds in alerts
- Field officers can register vehicles; gov+field create incidents directly (auto-broadcast); verified accidents section on public + logistics pages

## Iteration 6 (DONE — 2026-02) — Routing bugfix + report reputation
- BUGFIX: routes no longer dead-end — graph densified with local-road connectors (3 nearest towns, status LOCAL, gray, 'unverified' label) + direct-leg fallback; route line Google-blue with white casing, A/B teardrop pins
- Public report reputation: +10 tokens on verified report; 24h report ban on rejected (fake) report; tokens + ban state in /api/auth/me and public page UI
## Iteration 1 (DONE — 2026-02)
- Institutional white theme (deep teal-navy accent #1B4B66) per frontend spec §1-3
- Landing page (`/`) with hero, capabilities, role cards, region map SVG
- Login page (`/login`) with 4 role tabs (Government / Logistics / Field / Public), demo-fill, show/hide password, error handling
- JWT auth, bcrypt hashing, /api/auth/{login,me,demo-accounts}
- Owner + 5 demo accounts auto-seeded on startup
- Protected route stubs for /command-center, /logistics, /field, /public

## Iteration 2 (DONE — 2026-02) — Command Center
- `/command-center`: government dashboard — KPI strip (6 cards), MapLibre map (OSM desaturated base + road status layers + vehicle/incident markers), Live Incidents panel (severity-coded, source, confidence, relative time), Supply Risk strip (4 commodity cards), layer toggles, map legend, live indicator (10s polling), offline banner
- `/api/dashboard/summary` returns KPIs + roads GeoJSON + incidents + vehicles + supply (all tagged DEMO)
- Seeded demo dataset: 10 NER road corridors, 8 incidents, 12 vehicles, 8 villages, 4 supply commodities
- NavRail component (role-scoped icon rail) + stub routes for /map /vehicles /routes /incidents /supply /predictions /alerts /audit
- Fixed: MapLibre v6 named imports; maplibre CSS position:relative override fixed via inline style
- Fixed: NavRail now renders on PostLoginStub pages (role-scoped nav visible on /logistics etc.) — verified via retest

## Backlog (P1/P2)
- P1: WebSocket push replacing polling; GET /api/incidents dedicated endpoint; split server.py into routers
- P1: Real basemap style + corridor-accurate geometries (currently demo graph with synthetic local-road connectors)
- P2: Photo evidence upload (object storage), driver app, simulation sandbox, admin user management
- P2: Harden token/ban writes into transactions; store report_ban_until as Mongo datetime

## Auth
JWT (localStorage), 8h expiry, bcrypt. See /app/memory/test_credentials.md.
