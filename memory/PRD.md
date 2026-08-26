# NERIS — Product Requirements

## Original Problem
North Eastern Region Intelligence System (SIH26002). This iteration: white/institutional UI, beautiful login for Logistics Client and Government roles.

## Personas
- Government (Admin/Officer/District)
- Logistics Operator (fleet ops)
- Field Officer (mobile reporting)
- Public User (read-only)

## Iteration 1 (DONE — 2026-02)
- Institutional white theme (deep teal-navy accent #1B4B66) per frontend spec §1-3
- Landing page (`/`) with hero, capabilities, role cards, region map SVG
- Login page (`/login`) with 4 role tabs (Government / Logistics / Field / Public), demo-fill, show/hide password, error handling
- JWT auth, bcrypt hashing, /api/auth/{login,me,demo-accounts}
- Owner + 5 demo accounts auto-seeded on startup
- Protected route stubs for /command-center, /logistics, /field, /public

## Backlog (P0/P1)
- P0: Full Command Center with MapLibre map + live incidents + KPIs
- P0: Vehicles page + fleet routing
- P1: Predictions (Flood/Landslide/Accessibility)
- P1: Isolation map + Supply intelligence
- P2: Simulation, Alerts, Audit, Admin

## Auth
JWT (localStorage), 8h expiry, bcrypt. See /app/memory/test_credentials.md.
