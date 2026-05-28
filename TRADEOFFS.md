# Tradeoffs

Three things deliberately not built, and why.

---

## 1. CO₂ Calculation Engine

**What it would be:** Multiplying normalized quantities by emission factors (IPCC, DEFRA, EPA) to produce a kgCO₂e figure per record.

**Why we didn't build it:**

This is deceptively complex to do correctly. Emission factors vary by:
- Country and grid year (UK 2023 electricity grid intensity ≠ Germany 2023)
- Fuel type and combustion technology
- Flight class and distance band (short-haul vs long-haul economy have different DEFRA factors)
- Methodology version (GHG Protocol 2023 vs 2015 vs TCFD)

A hard-coded factor table would be wrong for any real client. The right architecture is a separate emission factor service (similar to what Watershed, Plan A, or Persefoni run internally) where factors are versioned, sourced, and auditable independently.

We built the data model to support it: `quantity_normalized` and `unit_normalized` are exactly the inputs the emission factor service would consume. Adding `co2e_kg` as a computed or stored field is a one-sprint addition once the factor source is decided.

**What I'd ask the PM:** "Where do your emission factors come from? DEFRA? IPCC AR6? Do they need to be versioned per reporting year?"

---

## 2. Real-Time / Scheduled API Ingestion

**What it would be:** A background worker (Celery + Redis) that polls SAP OData endpoints or Concur's API on a schedule, rather than waiting for manual file uploads.

**Why we didn't build it:**

This adds significant infrastructure: a task queue, a worker process, credential storage (encrypted secrets per DataSource), retry logic, dead-letter queues, and alerting on failed pulls. That's a full sprint of infrastructure work before writing a single API client.

More importantly, scheduled ingestion requires the client's IT team to provision service accounts, set up OAuth apps, and open firewall rules. For an onboarding prototype, file upload is the right starting point — it has zero dependencies on the client's infrastructure and can be up and running in an hour.

The `DataSource.config` JSONField is the hook for this: once we build an API connector for Concur, we store the credentials and schedule there. The `IngestionJob` model already supports non-file ingestion (the `upload` FK is nullable-ready conceptually).

---

## 3. Role-Based Access Control (RBAC)

**What it would be:** Distinct roles — `Analyst` (can review and approve), `Viewer` (read-only), `DataManager` (can upload, cannot approve), `AuditExport` (can export locked data to CSV/PDF for the auditor). Permissions enforced at the API level.

**Why we didn't build it:**

Every user is currently treated as an analyst with full read+approve permissions within their tenant. This is fine for a prototype with a single persona, but any real deployment needs at minimum a viewer role (for the sustainability lead who wants to see dashboards but shouldn't be clicking approve) and a separation between the person who uploads data and the person who approves it (four-eyes principle that many audit standards require).

Django's built-in permissions system (`django.contrib.auth.Permission`) or django-guardian (object-level permissions) would be the right implementation path. The `User` model is already custom (`AbstractUser`), so adding a `role` field is a one-migration change.

**What I'd ask the PM:** "Does the audit sign-off process require that the approver not be the same person who uploaded the data? If yes, we need RBAC before this goes to auditors."
