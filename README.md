# Breathe ESG — Emissions Data Ingestion Platform

A prototype Django REST + React application for ingesting, normalizing, and reviewing Scope 1/2/3 emissions activity data from three source types: SAP (fuel & procurement), utility portals (electricity), and corporate travel platforms (Concur/Navan).

## Live Demo

> **App:** https://breathe-esg.onrender.com  
> **Login:** `analyst` / `demo1234`

*(First load may take 30–60s — Render free tier cold start)*

## Repo Structure

```
Breathe_ESG/
├── backend/              # Django REST API
│   ├── config/           # settings, urls, wsgi
│   ├── core/             # models, views, serializers, ingestion logic
│   │   ├── management/commands/seed_demo.py
│   │   ├── models.py
│   │   ├── ingestion.py  # parse logic for SAP / Utility / Travel
│   │   ├── views.py
│   │   └── serializers.py
│   ├── requirements.txt
│   ├── Procfile
│   └── build.sh
├── frontend/             # Vite + React dashboard
│   └── src/
│       ├── pages/        # Login, Dashboard, Ingestion, Records, AuditLog
│       ├── components/   # Sidebar
│       └── api/          # Axios client
├── sample_data/          # Realistic CSV files for testing
│   ├── sap_sample.csv
│   ├── utility_sample.csv
│   └── travel_sample.csv
├── render.yaml           # Render.com one-click deploy blueprint
├── MODEL.md              # Data model documentation
├── DECISIONS.md          # Design decisions
├── TRADEOFFS.md          # Deliberate non-builds
└── SOURCES.md            # Source format research
```

## Local Development

### Prerequisites
- Python 3.11+
- Node 18+ / npm

### Backend

```bash
cd backend

# Create virtual env
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo    # creates analyst/demo1234
python manage.py runserver
```

API runs at **http://localhost:8000/api/**

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI runs at **http://localhost:5173/** (proxies `/api` to Django on port 8000)

### Upload Sample Data

1. Log in as `analyst` / `demo1234`
2. Go to **Ingest Data**
3. Upload `sample_data/sap_sample.csv` (source type: SAP)
4. Upload `sample_data/utility_sample.csv` (source type: Utility)
5. Upload `sample_data/travel_sample.csv` (source type: Travel)
6. Go to **Records Review** to approve rows

## Deployment (Render.com)

### Option 1 — One-Click Blueprint (recommended)

1. Push this repo to GitHub (can be private)
2. Go to [render.com/deploy](https://render.com) → New → Blueprint
3. Select your repository — Render reads `render.yaml` automatically
4. Click **Apply** — Render will:
   - Create a free PostgreSQL database
   - Deploy the web service (runs `build.sh` → builds React + runs migrations + seeds demo user)
5. Share the live URL

### Option 2 — Manual Deploy

1. Create a **PostgreSQL** database on Render (free tier)
2. Create a **Web Service**:
   - Root directory: `backend`
   - Build command: `./build.sh`
   - Start command: `gunicorn config.wsgi --workers 2`
3. Set environment variables:
   - `DATABASE_URL` → copy Internal Connection String from your PostgreSQL instance
   - `DJANGO_SECRET_KEY` → any long random string
   - `DJANGO_DEBUG` → `0`
   - `DJANGO_ALLOWED_HOSTS` → `.onrender.com`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login/` | Get auth token |
| GET | `/api/ingestions/` | List ingestion jobs |
| POST | `/api/ingestions/upload/` | Upload CSV (multipart) |
| GET | `/api/records/` | List normalized records (filterable) |
| PATCH | `/api/records/{id}/` | Edit a record (if not locked) |
| POST | `/api/records/{id}/approve/` | Approve & lock a record |
| POST | `/api/records/bulk_approve/` | Bulk approve by ID list |
| GET | `/api/raw-records/` | List raw parsed rows |
| GET | `/api/audit-events/` | Audit trail |

## Documentation

- **[MODEL.md](MODEL.md)** — Data model design and rationale
- **[DECISIONS.md](DECISIONS.md)** — Every design decision with alternatives considered
- **[TRADEOFFS.md](TRADEOFFS.md)** — Three deliberate non-builds and why
- **[SOURCES.md](SOURCES.md)** — Real-world format research for each source type
