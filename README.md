# Smart Irrigation Project

## Getting Started

1. Create and activate a virtual environment (optional but recommended)
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
```
2. Install dependencies
```bash
pip install -r backend/requirements.txt
```
3. Start the backend
```bash
python backend/app.py
```
4. Open the app in your browser at http://localhost:5000

## Modes (Simulation vs Hardware)

- The app supports two modes: `simulation` and `hardware`.
- Use the Hardware Mode toggle in the navbar to switch.
- Backend endpoints:
  - `GET /api/mode` → `{ "mode": "simulation" | "hardware" }`
  - `POST /api/mode` → `{ mode: "simulation" | "hardware" }`
- When in Hardware Mode, starting a simulation is disabled by the backend.
- `GET /api/sensors/latest` returns the newest sensor row stored.

## What's New (Improvements)

- Persistent simulation engine that doesn’t reset when navigating pages.
- Status & resume: Frontend resumes if a simulation is running.
- Reliable water usage updates with no-cache and cache-busting.
- Metrics APIs (last 24h): `/api/metrics/water_24h`, `/api/metrics/sensors_24h`.
- Status Report page with live, in-place updating charts.
- High-tech theme plus Light/Dark toggle (persisted).
- Dashboard Auto Scroll toggle (off by default).

## Pages

- Dashboard (`frontend/index.html`)
- Pump Control (`frontend/pages/pump-control.html`)
- Water Usage (`frontend/pages/water-usage.html`)
- Status Report (`frontend/pages/status-report.html`)

## Backend API Overview

- Simulation
  - `POST /api/simulation/start`
  - `POST /api/simulation/stop`
  - `GET /api/simulation/data`
  - `GET /api/simulation/status`
- Data
  - `GET /api/data/recent?limit=N`
  - `GET /api/water/usage`
  - `GET /api/sensors/latest`
- Metrics (24h)
  - `GET /api/metrics/water_24h`
  - `GET /api/metrics/sensors_24h`
- Mode
  - `GET /api/mode`
  - `POST /api/mode`
- Pump control
  - `POST /api/hardware/pump`

## Ideas to Make This a High-Class Project

- Auth/roles; per-zone irrigation; threshold config; alerts.
- Hardware streaming via WebSockets and real-time charts.
- CSV export; weekly/monthly analytics; Docker; CI tests.

## Development Notes

- DB: `backend/irrigation.db` (SQLite). Tables: `sensor_data`, `water_usage`.
- Pump ON step logs 2.0 L to `water_usage` during simulation.
- Frontend loads recent rows and total water on startup and resumes if running.
