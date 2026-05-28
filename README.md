# Breathe ESG — Emissions Data Ingestion Platform

> **Tech Intern Assignment Submission**  
> A prototype Django REST API + React dashboard for ingesting, normalising, and reviewing Scope 1/2/3 emissions activity data from three real-world source types.

---

## 🌐 Live Demo

| | |
|---|---|
| **App URL** | https://breathe-esg.onrender.com |
| **Login** | `analyst` / `demo1234` |
| **API root** | https://breathe-esg.onrender.com/api/ |

> ⚠️ Render free tier cold-starts in ~30–60s if the service has been idle. Just wait and refresh.

---

## 📋 What This Does

An analyst-facing tool that:

1. **Ingests** CSV files from three source types — SAP flat exports (fuel & procurement), utility portal exports (electricity), and corporate travel platform exports (flights, hotels, ground transport)
2. **Normalises** raw data into a canonical schema — unit conversion (MWh→kWh, gal→L), date parsing (ISO, German DD.MM.YYYY), Scope 1/2/3 categorisation
3. **Flags suspicious rows** automatically (negative quantities, missing IATA codes, future dates, missing billing periods)
4. **Surfaces a review dashboard** where analysts can inspect raw payloads, edit records, and approve rows — locking them immutably for audit

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Django 5.2 + Django REST Framework 3.15 |
| Auth | DRF Token Authentication |
| Database | PostgreSQL (Render) / SQLite (local dev) |
| File storage | Django FileField (local disk / Render disk) |
| Frontend | React 18 + Vite |
| HTTP client | Axios |
| Deployment | Render.com (blueprint via `render.yaml`) |
| Static files | WhiteNoise (served from Django) |

---

## 📁 Repository Structure

```
breathe-esg/
├── backend/
│   ├── config/                  # Django settings, URL root, WSGI
│   │   ├── settings.py
│   │   └── urls.py
│   ├── core/                    # Main app
│   │   ├── models.py            # Tenant, User, DataSource, IngestionJob,
│   │   │                        #   RawRecord, NormalizedRecord, AuditEvent
│   │   ├── ingestion.py         # CSV parsers for SAP / Utility / Travel
│   │   ├── views.py             # API viewsets — upload, approve, bulk_approve
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── tests.py             # 40 unit tests for all parsers
│   │   └── management/
│   │       └── commands/
│   │           └── seed_demo.py # Creates analyst/demo1234 on deploy
│   ├── migrations/
│   │   ├── 0001_initial.py
│   │   └── 0002_audit_event_index.py
│   ├── requirements.txt
│   ├── build.sh                 # Render build script
│   └── Procfile
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx    # Stats, scope breakdown, recent jobs
│       │   ├── Ingestion.jsx    # Drag-and-drop CSV upload
│       │   ├── Records.jsx      # Review table — filter, edit, approve
│       │   └── AuditLog.jsx     # Immutable audit trail
│       ├── components/
│       │   └── Sidebar.jsx
│       ├── api/client.js        # Axios instance with token auth
│       └── index.css            # Design system tokens + components
├── sample_data/
│   ├── sap_sample.csv           # 20 rows: fuel movements + procurement docs
│   ├── utility_sample.csv       # 12 rows: 5 meters, 3 months, 1 MWh row
│   └── travel_sample.csv        # 15 rows: flights, hotels, ground transport
├── render.yaml                  # One-click Render.com deploy blueprint
├── MODEL.md                     # ← Read this first
├── DECISIONS.md
├── TRADEOFFS.md
└── SOURCES.md
```

---

## 📖 Documentation (Read in This Order)

| File | Contents |
|---|---|
| **[MODEL.md](MODEL.md)** | Data model — every entity, every FK decision, scope assignment logic, key invariants |
| **[DECISIONS.md](DECISIONS.md)** | 7 design decisions: SAP format choice, utility ingestion mode, travel platform, approval model, suspicious detection, multi-tenancy |
| **[TRADEOFFS.md](TRADEOFFS.md)** | 3 deliberate non-builds: CO₂ calculation engine, real-time API ingestion, RBAC |
| **[SOURCES.md](SOURCES.md)** | Real-world format research for each of the 3 sources — what was researched, what was learned, what would break in production |

---

## 🚀 Local Development

### Prerequisites
- Python 3.11+
- Node 18+ / npm

### 1. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
pip install psycopg2-binary     # only needed if using PostgreSQL locally

# Set up the database and seed demo data
python manage.py migrate
python manage.py seed_demo      # creates: analyst / demo1234, Acme Corporation tenant

# Start the API server
python manage.py runserver
```

API available at → **http://localhost:8000/api/**

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

UI available at → **http://localhost:5173/**  
*(Vite proxies `/api/*` to Django on port 8000 — no CORS config needed locally)*

### 3. Upload Sample Data

1. Open **http://localhost:5173** and log in as `analyst` / `demo1234`
2. Go to **Ingest Data** → upload `sample_data/sap_sample.csv` → Source type: **SAP**
3. Upload `sample_data/utility_sample.csv` → Source type: **Utility**
4. Upload `sample_data/travel_sample.csv` → Source type: **Travel**
5. Go to **Records Review** — inspect suspicious rows, approve clean rows

Each sample file contains **intentional failure cases** to exercise the pipeline:
- `sap_sample.csv` — two rows with German date format (`DD.MM.YYYY`), one negative quantity
- `utility_sample.csv` — one row in MWh (tests unit conversion), one row with missing usage (tests failed-parse path)
- `travel_sample.csv` — two flights with missing distance (triggers `suspicious` flag)

---

## 🧪 Running Tests

```bash
cd backend
python manage.py test core --verbosity=2
```

**40 tests** across 5 test classes:

| Class | Coverage |
|---|---|
| `ParseDateTests` | ISO, German DD.MM.YYYY, slash DMY, empty, garbage |
| `ConvertQuantityTests` | MWh→kWh, gal→L, kWh passthrough, None input |
| `SapParserTests` | Fuel happy-path, procurement happy-path, German date, negative qty, missing date, invalid type |
| `UtilityParserTests` | Happy-path, MWh conversion, missing usage/meter/period, billing period separation, negative usage |
| `TravelParserTests` | All 3 trip types, missing distance, missing airports, invalid type, missing cost/currency/date, IATA uppercase |

---

## 🌍 Deployment (Render.com)

### Option 1 — One-Click Blueprint *(recommended)*

1. Fork or clone this repo to your GitHub account
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your GitHub repository — Render reads `render.yaml` automatically
4. Click **Apply**. Render will:
   - Provision a free **PostgreSQL** database
   - Deploy the web service: `build.sh` → installs deps → builds React → runs migrations → seeds demo user
5. Access your live URL (format: `https://breathe-esg.onrender.com`)

### Option 2 — Manual Deploy

1. Create a **PostgreSQL** database on Render (free tier)
2. Create a **Web Service**:
   - Root directory: `backend`
   - Build command: `./build.sh`
   - Start command: `gunicorn config.wsgi --workers 2 --timeout 120`
3. Set these environment variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | PostgreSQL internal connection string |
| `DJANGO_SECRET_KEY` | Any long random string (50+ chars) |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://your-app.onrender.com` |

---

## 🔌 API Reference

All endpoints require `Authorization: Token <token>` header (except login).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login/` | Get auth token — body: `{username, password}` |
| `GET` | `/api/ingestions/` | List ingestion jobs (paginated, tenant-scoped) |
| `POST` | `/api/ingestions/upload/` | Upload CSV — multipart: `source_type`, `file` |
| `GET` | `/api/records/` | List normalised records — filter: `?review_status=`, `?activity_type=`, `?job=` |
| `PATCH` | `/api/records/{id}/` | Edit a record (blocked if `locked_at` is set) |
| `POST` | `/api/records/{id}/approve/` | Approve & lock a single record |
| `POST` | `/api/records/bulk_approve/` | Bulk approve — body: `{ids: [1, 2, 3]}` |
| `GET` | `/api/raw-records/` | Immutable raw row payloads — filter: `?job=`, `?status=` |
| `GET` | `/api/audit-events/` | Full audit trail (append-only) |

### Example: Upload a CSV

```bash
curl -X POST https://breathe-esg.onrender.com/api/ingestions/upload/ \
  -H "Authorization: Token <your-token>" \
  -F "source_type=sap" \
  -F "file=@sample_data/sap_sample.csv"
```

### Example: Bulk Approve

```bash
curl -X POST https://breathe-esg.onrender.com/api/records/bulk_approve/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"ids": [1, 2, 3, 4]}'
```

---

## 🗂️ Data Model (Summary)

```
Tenant
  └── User (tenant FK)
  └── DataSource (type: sap | utility | travel)
       └── IngestionJob (tracks upload file + parse stats)
            └── RawRecord (immutable raw CSV row as JSON)
                 └── NormalizedRecord (canonical, editable until locked)
  └── AuditEvent (append-only log of every state change)
```

Key invariants:
- **Every queryset is filtered by `tenant`** — zero cross-tenant data bleed
- **Approved rows are immutable** — `locked_at` blocks all further edits via the API
- **Every NormalizedRecord traces to a RawRecord** — OneToOne enforced at DB level
- **AuditEvents are never updated or deleted** — write-once

See **[MODEL.md](MODEL.md)** for full entity definitions, FK decisions, and scope assignment logic.
