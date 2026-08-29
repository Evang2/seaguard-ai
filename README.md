
# SeaGuard AI

> **AI-assisted maritime intelligence platform for AIS vessel monitoring, anomaly detection, investigation prioritization, collision-risk analysis, historical playback, and continuous operational processing.**

**Status:** Active / ongoing development  
**Current state:** SeaGuard v1 operational platform completed through Milestone 10  
**Next:** live AIS simulation, then behaviour and route intelligence

---

## Overview

SeaGuard AI is a full-stack maritime intelligence platform built around **Automatic Identification System (AIS)** vessel data.

The project started with a simple question:

> How can raw vessel-position data be turned into useful, explainable maritime intelligence rather than just dots on a map?

SeaGuard processes AIS observations through several analytical layers:

```text
AIS observations
      │
      ▼
validation + normalization
      │
      ▼
trajectory / movement engineering
      │
      ├──────────────► deterministic anomaly detection
      │
      ├──────────────► Isolation Forest anomaly scoring
      │
      └──────────────► CPA/TCPA collision analysis
      │
      ▼
hybrid investigation priority
      │
      ▼
PostgreSQL / PostGIS persistence
      │
      ▼
FastAPI operational API
      │
      ▼
React + TypeScript dashboard
      │
      ├────────► CURRENT operational view
      │
      └────────► HISTORICAL playback
```

SeaGuard is designed to answer questions such as:

- Which vessels are behaving abnormally?
- Is the behaviour unusual according to deterministic maritime rules, machine learning, or both?
- Which observations deserve investigation first?
- Are two vessels on potentially dangerous trajectories?
- What happened at a specific historical point in time?
- What is happening in the latest active AIS state?
- Can newly arriving AIS data automatically trigger the complete analytics pipeline?

The project is intentionally built as a **software system**, not only as an ML notebook or proof-of-concept model.

---

# Key Features

## Continuous AIS ingestion

SeaGuard includes an operational file-ingestion pipeline built around an incoming AIS directory.

```text
data/incoming/
      │
      ▼
directory watcher
      │
      ▼
file stability check
      │
      ▼
SHA-256 content identity
      │
      ▼
import-job registry
      │
      ▼
AIS validation / persistence
      │
      ▼
automatic analytics
```

The ingestion system supports:

- automatic CSV discovery;
- file-stability detection before reading;
- SHA-256 hashing;
- duplicate-content protection;
- import-job tracking;
- `pending`, `completed`, and `failed` states;
- retry-safe processing;
- idempotent ingestion behaviour;
- post-import analytics orchestration.

A successful AIS import and successful analytics execution are intentionally treated as **separate operational outcomes**.

If AIS data is imported successfully but an analytics stage fails, the imported AIS data is not rolled back. This keeps ingestion resilient and makes secondary analytical failures observable rather than destructive.

---

## AIS validation and trajectory engineering

The AIS pipeline validates and normalizes vessel observations including:

- MMSI;
- timestamps;
- latitude;
- longitude;
- speed over ground (SOG);
- course over ground (COG);
- heading;
- navigation status.

Movement features are derived from consecutive reports **per vessel**, preventing one vessel's observations from contaminating another vessel's trajectory calculations.

Derived features include:

```text
elapsed_seconds
reporting_gap_minutes
distance_nm
calculated_speed_knots
speed_difference_knots
course_change_degrees
heading_change_degrees
acceleration_knots_per_minute
absolute_acceleration_knots_per_minute
turn_rate_degrees_per_minute
nonpositive_time_interval
```

Circular angles are handled correctly.

For example:

```text
359° → 1°
```

is interpreted as a:

```text
2°
```

change rather than `358°`.

This is important for course-change and heading-change detection.

---

# Deterministic Maritime Anomaly Detection

SeaGuard contains a rule-based anomaly engine for explainable maritime behaviour detection.

Current anomaly categories include:

- reporting gaps;
- position jumps;
- reported/calculated speed mismatch;
- rapid course changes;
- rapid heading changes;
- extreme acceleration or deceleration;
- non-positive time intervals;
- suspicious turns.

Representative thresholds include approximately:

```text
reporting gap               > 15 minutes
position-jump implied speed > 60 knots
speed disagreement          > 15 knots
course change               > 90°
heading change              > 90°
```

Additional acceleration and turning conditions are also applied.

Each persisted anomaly contains explainable evidence such as:

```text
anomaly_type
severity
metric_name
metric_value
threshold
message
```

This keeps rule-based alerts understandable to an operator instead of returning only opaque scores.

---

# Machine-Learning Anomaly Detection

SeaGuard uses **scikit-learn Isolation Forest** as its current unsupervised ML detector.

The feature set is based on vessel movement behaviour, including:

- SOG;
- reporting gap;
- distance travelled;
- calculated speed;
- speed disagreement;
- course change;
- heading change;
- absolute acceleration;
- turn rate.

Missing values are handled with median imputation.

The ML layer produces an anomaly score and anomaly classification.

## Important interpretation

The Isolation Forest output is **not treated as a probability that a vessel is dangerous**.

It is an **anomaly score**.

A more extreme score means that an observation is more unusual relative to the reference AIS population. It does not mean:

> “There is an X% probability that this vessel is dangerous.”

SeaGuard preserves that distinction throughout the application.

---

# Stable Live ML Baseline

SeaGuard does **not** retrain Isolation Forest on every small incoming AIS file.

That would make live scores unstable and statistically meaningless.

Instead, the current v1 design is:

```text
historical reference recording
          │
          ▼
derive trajectory features
          │
          ▼
fit Isolation Forest
          │
          ▼
calibrate hybrid percentile distribution
          │
          ▼
cache detector + assessor
          │
          └───────────────┐
                          │
new AIS observations     │
          │               │
          ▼               │
derive features           │
          │               │
          ▼               │
score using existing model
          │
          ▼
hybrid assessment
```

New observations are therefore scored against a **stable reference population**.

For v1 this provides a practical balance between:

- stability;
- determinism;
- simplicity;
- performance.

A later ML version will persist trained model artifacts and explicit model metadata.

---

# Hybrid Investigation Priority

Rule-based evidence and ML evidence are combined into a hybrid investigation layer.

Current investigation levels are:

```text
low
medium
high
critical
```

Persisted hybrid assessments include information such as:

```text
ml_anomaly_score
ml_anomaly_percentile
rule_flag_count
rule_severity
detector_agreement
risk_level
risk_reasons
assessment_version
```

The current assessment version is:

```text
hybrid-v1
```

## Detector agreement

SeaGuard records whether both analytical approaches agree:

```text
rule evidence
     +
ML anomaly evidence
     ↓
detector agreement
```

This allows operators to distinguish observations where:

- rules identified a maritime condition;
- ML found unusual statistical behaviour;
- both methods independently identified evidence.

## Investigation priority, not probability

The hybrid risk level is deliberately described as **investigation priority**.

It is not presented as:

- probability of criminal behaviour;
- probability of danger;
- certainty that a vessel is behaving incorrectly.

That distinction is important for explainability and responsible use.

---

# CPA / TCPA Collision Intelligence

SeaGuard includes a collision-analysis subsystem based on relative vessel motion.

It calculates:

- current vessel separation;
- **CPA — Closest Point of Approach**;
- **TCPA — Time to Closest Point of Approach**;
- relative speed;
- closing speed;
- bearing;
- collision investigation priority;
- explanatory reasons.

The collision subsystem is structured around components such as:

```text
collision/
├── geometry.py
├── risk.py
├── candidates.py
├── engine.py
├── persistence.py
└── current.py
```

Candidate vessel pairs are geographically restricted, typically to approximately:

```text
20 NM
```

AIS observations are also time-aligned, generally requiring reports to be within approximately:

```text
5 minutes
```

of each other.

Collision assessments use levels such as:

```text
low
medium
high
critical
```

The persisted assessment version is currently:

```text
cpa-tcpa-v1
```

### Important limitation

CPA/TCPA assumes motion based on the available AIS state and is an investigation aid.

SeaGuard does **not** claim that its collision priority is:

- a collision probability;
- a COLREGS determination;
- a substitute for professional navigation systems.

---

# Automatic Post-Ingestion Analytics

Milestone 10 completed the automatic intelligence pipeline.

After a successful AIS import, SeaGuard can automatically run:

```text
new AIS
  │
  ▼
trajectory context
  │
  ▼
deterministic anomaly detection
  │
  ▼
Isolation Forest scoring
  │
  ▼
hybrid investigation assessment
  │
  ▼
CPA/TCPA collision recomputation
  │
  ▼
persistent operational state
```

No manual anomaly, ML, hybrid-risk, or collision script is required for the normal ingestion workflow.

A key design detail is that live anomaly calculations load enough previous vessel history to calculate movement changes correctly.

For example, a newly imported observation cannot determine a reporting gap, acceleration, or position jump without the previous report for that vessel.

SeaGuard therefore:

1. loads the required trajectory context;
2. calculates features;
3. runs analytics;
4. persists analytics only for the newly imported observations.

---

# Current vs Historical Semantics

A major architectural problem solved during Milestone 10 was the difference between:

```text
latest-ever vessel state
```

and:

```text
currently active vessel state
```

A vessel whose last report was recorded in 2024 can still have that 2024 report as its **latest-ever** database observation.

That does not make the vessel currently active.

## AIS watermark

SeaGuard therefore defines a global AIS data watermark:

```text
watermark = MAX(AIS timestamp in the database)
```

For the current v1 operational model:

```text
active window = 15 minutes
active cutoff = watermark - 15 minutes
```

A vessel is active when:

```text
its latest observation >= active cutoff
```

This intentionally uses the **AIS data timeline**, not the computer's wall clock.

That makes the architecture compatible with:

- true live AIS;
- delayed data;
- simulated data;
- replayed recordings;
- historical test feeds.

---

## Current mode

The operational dashboard uses the active AIS watermark for:

- displayed vessels;
- moving-vessel counts;
- current collision encounters;
- hybrid-risk assessments;
- anomaly intelligence.

Conceptually:

```text
CURRENT
   │
   ├── active vessels
   ├── current anomalies
   ├── current hybrid risk
   └── current collision encounters
```

Historical database rows remain persisted.

They are not deleted simply because they are no longer active.

---

## Historical mode

Historical playback uses a separate state model:

```text
HISTORICAL
    │
    ├── historical playback snapshot
    ├── historical vessel trajectory
    ├── historical anomalies
    ├── historical hybrid risk
    └── historical collision evidence
```

When playback is active:

- dashboard mode changes to `HISTORICAL`;
- live polling is paused;
- playback owns the vessel-map state;
- historical investigation overlays are restricted to the replay context.

When playback exits, the application returns to the Current operational state.

---

# Historical AIS Playback

SeaGuard can replay a recorded AIS period as if the platform were observing maritime traffic over time.

Current playback API:

```http
GET /api/v1/playback/bounds
GET /api/v1/playback/snapshot
```

Playback controls include:

```text
play
pause
scrub
1×
4×
16×
60×
```

At the original design's `1×` setting:

```text
1 historical minute ≈ 1 real second
```

The snapshot logic uses a tolerance window so vessels with slightly asynchronous AIS reports can remain visible.

## Dense-recording selection

When synthetic/live test observations from 2026 were added to the database, a naive minimum/maximum timestamp query stretched playback from 2024 to 2026.

SeaGuard instead selects the **densest AIS recording day** for historical playback.

The current primary recording is:

```text
June 14, 2024
12,334 AIS observations
212 vessels
New York Harbor
```

This keeps historical playback anchored to a meaningful recording even when later test or live observations exist.

---

# Live Operational Dashboard

The React frontend exposes operational status such as:

- latest AIS timestamp;
- stored vessel count;
- AIS message count;
- last refresh;
- latest import;
- ingestion state.

The status bar can represent modes such as:

```text
LIVE
INGESTING
OFFLINE
HISTORICAL
```

Current operational data is polled approximately every:

```text
5 seconds
```

Selected-vessel investigation data is also refreshed in live mode.

The implementation includes safeguards against:

- overlapping requests;
- stale request races;
- clearing already-visible investigation data;
- loading-spinner flicker.

Abort controllers and request guards are used to preserve a stable investigation experience while new AIS information arrives.

---

# Investigation UI

The frontend is designed as an analyst-style dashboard rather than a simple map.

Current capabilities include:

## Global hybrid investigation overview

- critical count;
- high count;
- elevated count;
- detector-agreement count;
- priority filtering;
- ML percentile filtering;
- detector-agreement filtering;
- MMSI filtering;
- paginated investigation queue.

## Selected-vessel investigation

For a selected vessel, SeaGuard can display:

- latest position;
- trajectory;
- anomaly alerts;
- hybrid-risk assessments;
- risk explanations;
- collision encounters;
- correlated event timeline.

## Collision investigation

Collision cards expose:

- vessel A ↔ vessel B;
- risk level;
- current separation;
- CPA;
- TCPA;
- closing speed;
- relative speed.

## Map

The Leaflet map can visualize:

- active vessels;
- historical playback vessels;
- selected vessel state;
- trajectories;
- anomaly markers;
- risk markers;
- collision encounter lines.

---

# Dataset

The primary historical dataset currently used for development contains approximately:

```text
12,334 AIS observations
212 vessels
Recording date: June 14, 2024
Area: New York Harbor
```

The same recording is currently used for several purposes:

- historical playback;
- trajectory analysis;
- deterministic anomaly analysis;
- Isolation Forest reference/training data;
- hybrid-risk calibration;
- collision analysis.

Additional synthetic/test vessels have been inserted during continuous-ingestion and live-state development, so total database row counts may vary between development environments.

---

# Technology Stack

## Backend

- Python 3.12
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- PostGIS
- pandas
- NumPy
- scikit-learn
- Isolation Forest
- `uv`
- pytest
- Ruff

## Frontend

- React
- TypeScript
- Leaflet
- GeoJSON
- TypeScript compiler
- oxlint / project lint tooling

## Infrastructure / Workflow

- Docker
- Docker Compose
- PostgreSQL/PostGIS container
- Git
- GitHub
- VS Code

---

# Architecture

SeaGuard currently uses a **modular-monolith architecture**.

```text
SeaGuard AI
│
├── Backend
│   ├── FastAPI
│   ├── AIS processing
│   ├── ingestion
│   ├── deterministic anomalies
│   ├── ML
│   ├── hybrid risk
│   ├── CPA/TCPA collision engine
│   ├── playback
│   └── PostgreSQL/PostGIS persistence
│
├── Frontend
│   ├── React
│   ├── TypeScript
│   ├── Leaflet
│   ├── live operational dashboard
│   └── historical playback UI
│
└── Infrastructure
    ├── Docker / Compose
    ├── Alembic
    ├── pytest
    ├── Ruff
    └── GitHub
```

The project deliberately remains a modular monolith for now.

The goal is to maintain clear module boundaries without introducing distributed-system complexity before it is justified.

---

# Repository Structure

The project is organized approximately as follows:

```text
seaguard-ai/
│
├── backend/
│   ├── src/seaguard/
│   │   ├── api/
│   │   ├── ais/
│   │   ├── collision/
│   │   ├── db/
│   │   ├── ingestion/
│   │   ├── ml/
│   │   ├── risk/
│   │   └── ...
│   │
│   ├── scripts/
│   └── tests/
│
├── frontend/
│   └── src/
│
├── data/
│   ├── incoming/
│   ├── processed/
│   └── ...
│
├── docs/
│
└── Docker / project configuration
```

---

# Database Model

Important persisted entities include:

```text
vessels
ais_messages
anomaly_alerts
risk_assessments
collision_encounters
import_jobs
```

AIS messages contain fields such as:

```text
MMSI
timestamp
latitude
longitude
SOG
COG
heading
navigation status
PostGIS position
```

PostGIS is used for geospatial persistence and spatial operations.

Historical analytical records are intentionally retained even when they no longer represent the Current operational state.

---

# API Overview

SeaGuard exposes versioned endpoints under:

```text
/api/v1
```

Representative endpoints include:

## Health / operational state

```http
GET /api/v1/health
GET /api/v1/live/status
```

## Vessels / positions

```http
GET /api/v1/vessels
GET /api/v1/vessels/{mmsi}
GET /api/v1/vessels/{mmsi}/trajectory

GET /api/v1/positions/recent
```

Current-mode position queries can use active-state parameters such as:

```text
active_only=true
active_window_minutes=15
```

## Anomalies

```http
GET /api/v1/anomalies
```

Filtering supports concepts such as:

- MMSI;
- severity;
- anomaly type;
- time;
- current active window.

## Hybrid risk

```http
GET /api/v1/risk
GET /api/v1/risk/summary
GET /api/v1/risk/{mmsi}
```

Filtering supports:

- MMSI;
- risk level;
- minimum ML percentile;
- detector agreement;
- time;
- Current active window.

## Collision intelligence

```http
GET /api/v1/collisions
GET /api/v1/collisions/summary
GET /api/v1/collisions/{mmsi}
```

The API distinguishes current encounters from historical persisted encounters.

## Historical playback

```http
GET /api/v1/playback/bounds
GET /api/v1/playback/snapshot
```

---

# Running Locally

> The commands below reflect the current development workflow. Exact infrastructure startup may depend on the repository's Docker Compose configuration.

## Prerequisites

Recommended local tools:

- Git
- Docker
- Docker Compose
- Python 3.12
- `uv`
- Node.js
- npm

Clone the repository:

```bash
git clone <your-repository-url>
cd seaguard-ai
```

## Start infrastructure

Start the PostgreSQL/PostGIS services defined by the project:

```bash
docker compose up -d
```

Apply database migrations as required:

```bash
cd backend
uv run alembic upgrade head
```

## Backend

From the backend directory:

```bash
cd backend
uv sync
uv run uvicorn seaguard.main:app --reload
```

FastAPI documentation is available through the application's `/docs` route while the backend is running.

## Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev -- --force
```

---

# Development Quality Checks

## Backend

```bash
cd backend

uv run ruff format .
uv run ruff check .
uv run pytest -v
```

## Frontend

```bash
cd frontend

npm run build
npm run lint
```

A milestone is not considered complete until the relevant backend and frontend checks pass.

---

# Example Development Workflow

A typical SeaGuard development session is:

```text
1. Start PostgreSQL/PostGIS
2. Start FastAPI
3. Start React frontend
4. Start AIS directory watcher
5. Place or generate AIS data in data/incoming/
6. Watch ingestion complete
7. Observe automatic analytics
8. Inspect Current dashboard
9. Use historical playback for historical investigation
10. Run backend/frontend regression checks before committing
```

---

# Design Decisions

## 1. Keep historical records

SeaGuard does not delete historical anomaly, risk, or collision records merely because a vessel is no longer active.

Operational state and historical evidence are separate concepts.

## 2. Use an AIS watermark instead of wall-clock time

Current mode is based on the latest AIS timestamp in the database rather than `datetime.now()`.

This supports real, delayed, simulated, and historical feeds consistently.

## 3. Do not retrain ML for every incoming file

Live files can contain only one or a few observations.

Refitting an unsupervised model on such small batches would produce unstable results.

SeaGuard scores new data against a stable baseline instead.

## 4. Keep import success separate from analytics success

An analytics failure should not destroy valid AIS data that was already successfully ingested.

## 5. Preserve explainability

Rules expose thresholds and metric values.

Hybrid risk exposes rule evidence, ML percentile, detector agreement, and reasons.

## 6. Polling before WebSockets

Five-second polling is sufficient for the current v1 architecture.

WebSockets or SSE are deliberately deferred until push-based transport provides a clear operational benefit.

---

# Project Status

## SeaGuard v1 operational platform

Milestones 0–10 are now treated as the first complete operational version of SeaGuard.

| Milestone | Area | Status |
|---|---|---|
| 0 | Project foundation | ✅ Complete |
| 1 | AIS ingestion and cleaning | ✅ Complete |
| 2 | Rule-based anomaly detection | ✅ Complete |
| 3 | Maritime persistence and API | ✅ Complete |
| 4 | Isolation Forest ML detection | ✅ Complete |
| 5 | Hybrid investigation priority | ✅ Complete |
| 6 | CPA/TCPA collision intelligence | ✅ Complete |
| 7 | Historical AIS playback | ✅ Complete |
| 8 | Continuous AIS ingestion | ✅ Complete |
| 9 | Live operational dashboard | ✅ Complete |
| 10 | Full live intelligence pipeline and Current/Historical semantics | ✅ Complete |
| 11 | Behaviour and route intelligence | ⏳ Planned |
| 12 | ML v2 | ⏳ Planned |
| 13 | Geospatial maritime intelligence | ⏳ Planned |
| 14 | Investigation workflow | ⏳ Planned |
| 15 | Authentication / RBAC | ⏳ Planned |
| 16 | WebSockets / SSE | ⏳ Planned |
| 17 | Production hardening | ⏳ Planned |
| 18 | Deployment | ⏳ Planned |
| 19 | Portfolio / product polish | ⏳ Planned |

---

# What I Am Building Next

SeaGuard is an ongoing project.

The current platform has the operational architecture required to ingest AIS data and automatically run anomaly, ML, hybrid-risk, and collision analysis.

The next work focuses on making the system more realistic to demonstrate and more sophisticated analytically.

---

## Next Step — Live AIS Simulator

Before beginning the advanced behaviour models, the next planned development task is a **live AIS simulation harness**.

The project currently has a real historical recording but does not depend on a commercial live AIS provider.

The simulator will replay historical observations as timed incoming AIS data:

```text
historical AIS recording
          │
          ▼
simulation engine
          │
          ▼
timestamp remapping
          │
          ▼
small timed AIS batches
          │
          ▼
data/incoming/
          │
          ▼
existing SeaGuard ingestion pipeline
          │
          ▼
rules + ML + hybrid risk + CPA/TCPA
          │
          ▼
LIVE dashboard
```

### Simulator goals

The simulator is planned to support:

- replaying the real historical vessel recording as a pseudo-live feed;
- remapping historical timestamps onto the current simulation timeline;
- preserving relative time intervals between AIS observations;
- configurable replay speed;
- configurable batch size;
- deterministic development/demo runs;
- clean shutdown;
- safe file naming and ingestion identity;
- controlled synthetic scenarios;
- automatic use of the existing ingestion watcher.

This will allow SeaGuard to demonstrate real operational behaviour without pretending that a static historical file is a genuine live AIS feed.

---

## Future Real AIS Integration

The longer-term ingestion design will make the AIS source replaceable.

Conceptually:

```text
CSV directory source ─────┐
                          │
historical simulator ─────┼────► normalized AIS observations
                          │
synthetic generator ──────┤
                          │
real AIS provider ────────┘
                                   │
                                   ▼
                            SeaGuard pipeline
```

Possible source adapters could eventually include:

```text
CsvDirectorySource
HistoricalReplaySource
SyntheticAISSource
LiveAISProviderSource
```

The analytical pipeline should not need to know which source produced an observation.

---

# Milestone 11 — Behaviour and Route Intelligence

This is the next major analytical milestone.

The goal is to move beyond isolated movement anomalies and model **how vessels normally behave over time**.

Planned work includes:

## Vessel behaviour profiles

Learn typical behaviour by vessel and/or vessel class, including:

- typical speed;
- typical operating areas;
- typical routes;
- typical reporting patterns;
- typical ports;
- typical anchorages.

## Route deviation detection

Detect vessels departing significantly from expected or previously observed movement corridors.

## Loitering detection

Identify vessels remaining unusually long inside a small geographic area.

## Unexpected stopping

Detect stationary behaviour outside expected locations such as:

- ports;
- anchorages;
- known waiting areas.

## Abnormal rendezvous behaviour

Identify unusual close interactions between vessels.

## Behaviour-risk explanations

Explain *why* current behaviour differs from expected patterns rather than providing only an anomaly score.

---

# Milestone 12 — ML v2

The second ML phase will move beyond the current Isolation Forest runtime.

Planned work includes:

## Persistent model artifacts

Move from process-start fitting toward:

```text
train
  ↓
version
  ↓
persist
  ↓
load
  ↓
score
```

## Model metadata

Track information such as:

```text
model version
training timestamp
training dataset
feature set
hyperparameters
evaluation information
```

## Controlled retraining

Add an explicit retraining workflow rather than accidental or implicit retraining during ingestion.

## Vessel-class-aware modelling

Different vessel classes have different normal behaviour.

Future models should account for vessel categories such as:

- cargo;
- tanker;
- tug;
- passenger;
- fishing;
- other classes.

## ML evaluation dashboard

Compare over time:

```text
deterministic rules
vs
ML
vs
hybrid assessment
```

---

# Milestone 13 — Geospatial Maritime Intelligence

Planned geospatial intelligence includes:

- ports;
- anchorage zones;
- shipping lanes;
- restricted areas;
- operator-defined geofences;
- geographic context for anomaly interpretation.

For example:

```text
rapid course change in open water
```

should not necessarily carry the same context as:

```text
rapid course change in a congested harbour
```

---

# Milestone 14 — Investigation Workflow

The long-term goal is for SeaGuard to become an analyst-oriented investigation tool rather than only a detection dashboard.

Planned capabilities include:

## Alert state

```text
new
reviewing
resolved
dismissed
```

## Analyst notes

Attach human investigation notes to:

- vessels;
- anomaly events;
- risk observations;
- collision encounters.

## Cases

Group multiple pieces of evidence into a single investigation:

```text
vessel
+
anomalies
+
risk observations
+
collision encounters
+
notes
```

## Event correlation

Correlate future intelligence such as:

```text
route anomaly
+
ML anomaly
+
collision risk
+
geofence event
```

---

# Milestone 15 — Authentication and RBAC

Authentication is intentionally deferred until the core intelligence platform is mature.

Planned roles may include:

```text
viewer
analyst
administrator
```

Potential permissions will control:

- investigation updates;
- notes;
- case management;
- administrative functions;
- model operations.

---

# Milestone 16 — True Real-Time Transport

Current five-second polling is sufficient for SeaGuard v1.

Later versions may add WebSockets or Server-Sent Events for:

- vessel-position updates;
- anomaly events;
- hybrid-risk changes;
- collision encounters;
- ingestion-status events.

The frontend can then move toward incremental state updates rather than refreshing the whole current fleet.

---

# Milestone 17 — Production Hardening

Planned production work includes:

- structured logging;
- metrics;
- database/index review;
- API latency monitoring;
- ingestion metrics;
- analytics-duration metrics;
- ML scoring metrics;
- collision-engine metrics;
- error monitoring;
- query optimization;
- improved health checks;
- background-job architecture if ingestion volume requires it.

---

# Milestone 18 — Deployment

Planned deployment work includes:

- production Docker configuration;
- backend hosting;
- PostgreSQL/PostGIS hosting;
- frontend hosting;
- HTTPS;
- domain configuration;
- environment/secrets management.

---

# Milestone 19 — Product and Portfolio Polish

The final portfolio phase will include:

- refined README and technical documentation;
- architecture diagrams;
- polished screenshots;
- demo video;
- one-command demo environment;
- demo dataset;
- documented ML methodology;
- documented CPA/TCPA methodology;
- documented live-ingestion architecture;
- CV/portfolio project summary.

This README is part of that ongoing documentation effort and will continue to evolve with the project.

---

# Disclaimer

SeaGuard AI is currently a development and portfolio project.

Its anomaly scores, hybrid investigation priorities, and CPA/TCPA assessments are intended for experimentation, software engineering, and decision-support research.

They must not be interpreted as:

- proof of wrongdoing;
- probability that a vessel is dangerous;
- an official navigational warning;
- a COLREGS determination;
- a substitute for certified maritime navigation or safety systems.

---

# Ongoing Development

SeaGuard is actively evolving.

The current v1 platform establishes the complete operational foundation:

```text
ingestion
  ↓
trajectory intelligence
  ↓
rule anomalies
  ↓
ML anomalies
  ↓
hybrid investigation priority
  ↓
collision intelligence
  ↓
persistent API
  ↓
Current + Historical dashboard
```

The next phase expands this foundation toward:

```text
live simulation
      ↓
behaviour profiles
      ↓
route intelligence
      ↓
geospatial context
      ↓
analyst workflow
      ↓
production deployment
```

The objective is to progressively turn SeaGuard from an AIS analytics project into a more complete **maritime intelligence and investigation platform**.
