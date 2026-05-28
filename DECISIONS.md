# Decisions

Every significant ambiguity resolved during the build, with reasoning and honest acknowledgement of what was left open.

---

## D1 — SAP Export Format: Which Interface?

**Options considered:**
- IDoc (Intermediate Document) — SAP's native EDI format, XML or fixed-width
- OData service (SAP Gateway) — REST-like, JSON or XML, requires SAP NetWeaver Gateway
- BAPI / RFC call — programmatic, not a file format
- Flat file / CSV extract — produced by SAP via SE16N, SQ01, or custom ABAP report

**Chosen option:** Flat file CSV (SE16N / custom ABAP extract)

**Why:**
- IDocs are the right answer for real-time system integration but require an IDoc adapter on our side, which is weeks of work. They also need a partner agreement configured in SAP.
- OData requires SAP Gateway to be licensed and configured, and the client's SAP team to expose the right OData service. Many older SAP landscapes (ECC 6.0) don't have this out of the box.
- BAPI/RFC requires direct RFC connectivity to the SAP system — a network and firewall problem before it's a code problem.
- Flat file CSVs are what every SAP client can produce today with no configuration: a consultant opens SE16N on table EKKO (purchase orders) or a custom MB51 movement report and exports to .csv or .xlsx. This is the most realistic "we need your data by Friday" path.

**What we're explicitly handling:**
- Document date (`BLDAT`) in ISO or German DD.MM.YYYY format
- Quantity + unit for fuel movements
- Amount + currency for procurement documents
- Plant code, vendor, material description, SAP document number

**What we're explicitly not handling:**
- Multi-currency documents (we take the document currency as-is)
- German column header variants (e.g. `Menge` instead of `quantity`) — we require a known header set
- SAP company code / controlling area hierarchy
- Reversal documents (negative postings) — they'll pass through as suspicious (negative quantity)

**What I'd ask the PM:**
- "Does the client have an ABAP developer who can maintain the extract query, or will they be pulling it manually from SE16N each month?"
- "Is this ECC 6.0 or S/4HANA? (S/4HANA has better standard reporting, IDoc profiles differ)"
- "Do they need us to handle reversal documents, or should those be excluded at source?"

---

## D2 — Utility Data: Portal CSV vs PDF Bill vs API

**Options considered:**
- PDF bill parsing — high fidelity to real-world but requires OCR/PDF parsing, fragile across utility vendors
- Utility API (e.g. ESPI/Green Button standard, or utility-specific APIs like PG&E Share My Data) — cleanest but requires OAuth setup per utility, limited availability outside US
- Portal CSV export — every major utility offers a download; format varies but is structured

**Chosen option:** Portal CSV export

**Why:**
- PDF parsing has too high a failure rate for different bill layouts. Every utility formats their PDF differently. We'd need a template per utility.
- Green Button / ESPI is US-centric and requires per-utility OAuth integration. Most European utilities don't support it.
- Portal CSVs are universally available, structured enough to parse reliably, and match what a facilities team actually does today: log in to the utility portal once a month and hit "Export".

**What we're explicitly handling:**
- Meter ID, facility name, billing period (start + end), usage (kWh or MWh), tariff code
- Billing periods that don't align with calendar months (we store `period_start` / `period_end` separately from `occurred_on`)
- MWh → kWh unit conversion

**What we're explicitly not handling:**
- Reactive power / power factor charges
- Multiple tariff bands within one billing period (peak vs off-peak breakdown)
- Estimated vs actual reads (we treat all reads as actual)
- Negative usage (net metering / solar export) — flagged as suspicious

**What I'd ask the PM:**
- "Are any of the client's facilities net-metered / have on-site solar? Negative usage would be normal there."
- "Do they have multiple utilities across regions? We'd need to handle different CSV schemas per utility."

---

## D3 — Corporate Travel: Concur vs Navan vs Direct Export

**Options considered:**
- Concur API (SAP Concur) — well-documented, OAuth 2.0, JSON
- Navan (TripActions) API — REST API with webhooks
- Direct platform CSV export — what every platform supports without API integration

**Chosen option:** CSV export from the travel platform

**Why:**
- API integration requires OAuth credential management, webhook infrastructure, and resilience handling — all out of scope for a 4-day prototype.
- The CSV export is what a travel manager actually does to run end-of-quarter reports. Both Concur and Navan support it.
- Our ingestion schema is designed to match what these exports actually contain (trip type, booking date, origin/destination IATA codes, cost, vendor, ticket class).

**What we're explicitly handling:**
- Flights: IATA origin/destination codes, distance (when provided), ticket class, cost
- Hotels: cost, vendor, nights (stored as `quantity` with an implicit unit of "nights")
- Ground transport: distance (when provided), cost, vendor
- Missing distance on flights — flagged as suspicious, analyst reviews

**What we're explicitly not handling:**
- Train travel (common in Europe, large emissions difference vs flights)
- Taxi/rideshare with no distance data
- Multi-leg itineraries — we treat each booking line as one record
- Personal car mileage reimbursement claims

**What I'd ask the PM:**
- "Does the client use Concur or something else? Concur exports have a specific column set."
- "Do they need rail travel categorized separately? Significant for UK/EU clients."

---

## D4 — Ingestion Mechanism: File Upload vs API Pull vs Paste

**Chosen option:** File upload (multipart form)

**Why:** It's the lowest-friction path for all three source types. The client's sustainability team already has these files; they just need somewhere to upload them. API pull would require storing credentials per source and running scheduled tasks — that's infrastructure complexity that doesn't add value in a prototype. Manual paste is worse UX and harder to validate.

---

## D5 — Approval Model: Row-by-Row vs Batch

**Chosen option:** Both. Individual approve (`POST /api/records/{id}/approve/`) and bulk approve (`POST /api/records/bulk_approve/`).

**Why:** An analyst will want to bulk-approve clean rows and individually review suspicious ones. The API supports both; the UI exposes both.

**What I'd ask the PM:**
- "Should approval require a second approver (four-eyes principle)? Auditors sometimes require this."

---

## D6 — Suspicious Record Detection

Rows are automatically flagged as `suspicious` if any of:
- `quantity_normalized < 0` (negative quantities — could be reversal documents)
- Flight record with no origin or destination IATA code
- Electricity record with no billing period
- `occurred_on` is in the future
- No unit after normalization

**What I'd ask the PM:**
- "Do you want outlier detection (e.g. quantity > 3 standard deviations from monthly average)? Out of scope here but a natural next step."

---

## D7 — Multi-tenancy Implementation

**Chosen option:** Shared database, tenant FK on every table (row-level isolation, not schema-per-tenant).

**Why:** Schema-per-tenant (PostgreSQL schemas) is more isolated but requires dynamic migrations and a more complex ORM setup. For a prototype with a small number of tenants, shared-database with FK isolation is standard practice (used by Stripe, Shopify, etc.). Every queryset in the codebase is filtered by `tenant=request.user.tenant`.

**What I'd ask the PM:**
- "Are there data residency requirements that would require separate databases per client? (GDPR, ISO 27001)"
