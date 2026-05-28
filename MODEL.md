# Data Model

## Design Goals

The model must satisfy five hard requirements from the assignment:

1. **Multi-tenancy** — each client's data is strictly isolated
2. **Scope 1/2/3 categorisation** — every activity row carries a GHG scope label
3. **Source-of-truth tracking** — every normalized row traces back to an exact raw row and the ingestion job that created it
4. **Unit normalisation** — raw quantities in any unit are converted to a canonical unit before storage
5. **Audit trail** — every state change (ingest, edit, approve) is recorded immutably

---

## Entity Reference

### `Tenant`

Represents a single client company. All other entities are scoped to a tenant via a FK, so there is zero cross-tenant data bleed at the query level.

```
Tenant
  id          BigAutoField (PK)
  name        CharField(200)
  slug        SlugField(100, unique)
  created_at  DateTimeField (auto)
  updated_at  DateTimeField (auto)
```

**Why slug?** Used in API paths and log messages. Stable and human-readable.

---

### `User`

Extends Django's `AbstractUser`. Adds a mandatory FK to `Tenant`. A superuser can have `tenant=NULL` (admin only, no data access through the API).

```
User (extends AbstractUser)
  tenant   FK → Tenant (PROTECT, nullable for superusers)
  ...standard Django user fields...
```

**Why PROTECT?** Prevents accidental cascade deletion of a tenant from silently deleting all analyst accounts.

---

### `DataSource`

Represents a named feed from one source type (SAP, Utility, Travel) for a tenant. A tenant may have multiple SAP feeds (e.g. one per SAP system). Unique constraint: `(tenant, type, name)`.

```
DataSource
  id      BigAutoField (PK)
  tenant  FK → Tenant (CASCADE)
  type    CharField choices: sap | utility | travel
  name    CharField(200)
  config  JSONField  — reserved for future API credentials / mapping overrides
```

**Why JSONField config?** Keeps the model stable while allowing source-specific metadata (e.g. meter→facility mappings) without schema churn.

---

### `IngestionJob`

One upload or pull event. Tracks processing stats and file provenance.

```
IngestionJob
  id               BigAutoField (PK)
  tenant           FK → Tenant (CASCADE)
  source           FK → DataSource (PROTECT)
  created_by       FK → User (SET_NULL)
  status           CharField: received | parsed | failed
  upload           FileField  — the original uploaded file stored on disk
  total_rows       PositiveIntegerField
  parsed_rows      PositiveIntegerField
  failed_rows      PositiveIntegerField
  suspicious_rows  PositiveIntegerField
  approved_rows    PositiveIntegerField
  created_at       DateTimeField (auto)
  updated_at       DateTimeField (auto)
```

**Why store the original file?** Auditors need to see the exact bytes that were ingested. We never re-parse from the stored file — it's an archive.

**Why PROTECT on source?** You should not be able to delete a DataSource that has historical ingestions hanging off it.

---

### `RawRecord`

One row from the uploaded file, stored as-is in a JSONField. This is the immutable source-of-truth; it never changes after creation.

```
RawRecord
  id          BigAutoField (PK)
  tenant      FK → Tenant (CASCADE)
  job         FK → IngestionJob (CASCADE)
  row_number  PositiveIntegerField  — 1-indexed line in the original file
  payload     JSONField  — raw key:value dict as parsed from CSV
  status      CharField: parsed | failed
  errors      JSONField  — list of error codes
  warnings    JSONField  — list of warning codes
  created_at  DateTimeField (auto)
  updated_at  DateTimeField (auto)

  Indexes: (tenant, job, row_number), (tenant, status)
```

**Why store raw payload?** If our normalization logic has a bug, we can re-parse without losing the original data. This is the source-of-truth.

---

### `NormalizedRecord`

The analyst-facing, editable representation of one activity event. Has a 1:1 relationship with `RawRecord`.

```
NormalizedRecord
  id                  BigAutoField (PK)
  tenant              FK → Tenant (CASCADE)
  job                 FK → IngestionJob (CASCADE)  — denormalized for faster filtering
  raw_record          OneToOneField → RawRecord (CASCADE)

  # Scope & activity
  scope               CharField: scope1 | scope2 | scope3
  activity_type       CharField: fuel | procurement | electricity | flight | hotel | ground

  # Time
  occurred_on         DateField (nullable)   — point-in-time events (SAP docs, travel)
  period_start        DateField (nullable)   — for billing-period data (utility)
  period_end          DateField (nullable)

  # Quantity (raw and normalised)
  quantity            DecimalField(18,6)     — as received
  unit                CharField(50)          — as received (normalised spelling)
  quantity_normalized DecimalField(18,6)     — converted to canonical unit
  unit_normalized     CharField(50)          — canonical: kWh, L, km

  # Cost
  cost_amount         DecimalField(18,2)
  currency            CharField(10)

  # Descriptive
  description         CharField(500)
  location            CharField(200)         — plant code or facility name
  vendor              CharField(200)
  origin              CharField(10)          — IATA code for flights
  destination         CharField(10)          — IATA code for flights

  # Quality flags
  suspicious          BooleanField
  suspicious_reasons  JSONField              — list of reason codes
  review_status       CharField: pending | suspicious | approved

  # Audit lock
  locked_at           DateTimeField (nullable)  — set on approve, immutable after
  approved_at         DateTimeField (nullable)
  approved_by         FK → User (SET_NULL)

  # Escape hatch
  metadata            JSONField  — source-specific fields (SAP doc number, meter ID, etc.)

  created_at          DateTimeField (auto)
  updated_at          DateTimeField (auto)

  Indexes: (tenant, review_status), (tenant, suspicious), (tenant, activity_type)
```

**Key invariant:** Once `locked_at` is set, no field may be updated. The `approve()` method sets `locked_at` and `review_status = approved` atomically. Any correction after approval must be a new NormalizedRecord (corrective entry), not an edit.

**Why two quantity fields?** `quantity` preserves the source value for auditability. `quantity_normalized` enables cross-source aggregation (e.g. MWh → kWh → emissions). An analyst can see both.

**Why `metadata` JSONField?** Source-specific fields (SAP document number, meter ID, ticket class) don't belong in the normalised schema. They go in `metadata` so they're queryable without bloating the core table.

---

### `AuditEvent`

Immutable log of every state change. Never updated or deleted.

```
AuditEvent
  id           BigAutoField (PK)
  tenant       FK → Tenant (CASCADE)
  actor        FK → User (SET_NULL)
  action       CharField: ingestion_created | record_created | record_edited | record_approved
  entity_type  CharField(100)  — "IngestionJob" or "NormalizedRecord"
  entity_id    CharField(100)  — PK of the referenced entity
  before       JSONField (nullable)  — snapshot before edit
  after        JSONField (nullable)  — snapshot after edit / creation payload
  created_at   DateTimeField (auto)
```

**Why not use Django signals?** Signals are implicit and hard to test. We call `AuditEvent.objects.create(...)` explicitly at each mutation site in the view, making the audit trail easy to reason about and trace.

---

## Scope Assignment Logic

| Activity Type | GHG Scope | Rationale |
|---|---|---|
| Fuel (combustion) | Scope 1 | Direct emissions from owned/controlled sources |
| Electricity | Scope 2 | Indirect emissions from purchased energy |
| Procurement | Scope 3 | Value chain — purchased goods and services |
| Flights | Scope 3 | Business travel (Category 6) |
| Hotels | Scope 3 | Business travel (Category 6) |
| Ground transport | Scope 3 | Business travel (Category 6) |

---

## Key Invariants

1. **Approved rows are immutable.** `locked_at != null` means the row cannot be edited via the API. Corrections go through new revision rows.
2. **Every NormalizedRecord must trace to a RawRecord.** The OneToOneField enforces this at the DB level.
3. **All data is tenant-scoped.** Every queryset is filtered by `tenant=request.user.tenant`. There is no cross-tenant join.
4. **Audit events are append-only.** There is no update or delete path for `AuditEvent` in the API.
5. **Unit normalisation is canonical.** `unit_normalized` is always one of: `kWh`, `L`, `km`, or the original unit if no conversion is defined. `MWh → kWh` and `gal → L` conversions are applied on ingest.
