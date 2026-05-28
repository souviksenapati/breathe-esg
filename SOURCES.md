# Sources Research

For each source type: what format was researched, what was learned, what the sample data looks like and why, and what would break in real deployment.

---

## 1. SAP (Fuel + Procurement)

### What format was researched

SAP exposes data through several interfaces, in increasing complexity:

1. **SE16N / table browser exports** — A user opens transaction SE16N, queries a table (e.g., MSEG for material documents, EKKO/EKPO for purchase orders), and exports to .csv or .xlsx. No technical setup required. The export reflects the raw SAP table columns, which are in English or German depending on the system language setting.

2. **SQ01 / ABAP query reports** — A more structured path: a consultant writes an ABAP query joining multiple tables (e.g., EKKO + EKPO + LFA1 for a PO with vendor details) and the user runs it as a report. Outputs to .csv or .xlsx. Column names are defined by the ABAP developer.

3. **IDoc (Intermediate Document)** — SAP's native EDI format. Used for real-time system-to-system integration. IDoc files are either fixed-width (classic EDI) or XML. The segment structure is highly specific to the IDoc type (e.g., MATMAS05 for materials, ORDERS05 for purchase orders). Requires an IDoc adapter on the receiving side.

4. **OData service (SAP Gateway)** — REST-like API exposing SAP entities as OData entities. Available in S/4HANA out of the box; requires SAP Gateway license + configuration in older ECC 6.0. Returns JSON or XML.

5. **BAPI / RFC** — Programmatic function module calls directly to SAP. Requires RFC network connectivity and SAP GUI or JCo library.

**We chose flat file CSV (option 1/2)** — see DECISIONS.md D1.

### What was learned

**Key gotchas from SAP exports:**

- **Date formats**: SAP stores dates internally as YYYYMMDD (8-digit integer). When exported through SE16N, the display format depends on the user's SAP date format setting. German systems default to `DD.MM.YYYY`. An English language system may output `MM/DD/YYYY` or `YYYY-MM-DD`. A single export from a multi-language system can have mixed formats in the same column.

- **German column headers**: In a German-language SAP system, `Menge` = quantity, `Einheit` = unit, `Datum` = date, `Betrag` = amount, `Buchungskreis` = company code. A procurement export from a German subsidiary may arrive with German headers.

- **Plant codes mean nothing without a lookup**: `DE01`, `DE02`, `US-CHI` are internal SAP plant identifiers. Their human-readable names (`Frankfurt Main Plant`, `Munich Assembly Plant`) live in table T001W. The export doesn't include this by default.

- **Units are SAP-specific**: SAP uses its own unit codes. `L` = liter, `ST` = piece, `KG` = kilogram, `M3` = cubic meter. They overlap with SI units but are not identical.

- **Amounts are in document currency**: SAP stores the amount in the document currency (the currency of the vendor invoice), not the group currency. Multi-currency consolidation requires FX rate tables (TCURR in SAP).

- **Reversal documents**: SAP allows reversing a goods movement or invoice. The reversal creates a new document with a negative quantity. Both the original and the reversal appear in a standard extract unless the ABAP query explicitly filters them out.

### What the sample data looks like and why

`sap_sample.csv` contains 20 rows: 10 fuel movements and 10 procurement documents.

**Fuel rows**: Diesel EN590 (the European standard for road diesel), petrol 95, LPG, and one HVO100 (a biofuel common in Germany) from different plant codes (DE01, DE02, DE03 representing Frankfurt, Munich, Hamburg). Quantities in liters. Two rows use German date format (`05.02.2024`, `14.02.2024`) to test date parsing resilience.

**Procurement rows**: A realistic mix of procurement categories — office supplies, industrial packaging, IT hardware, chemical cleaning agents, maintenance services, raw materials (steel), safety equipment, freight logistics. Amounts in EUR. One row for Bilfinger SE uses German date format. GL account codes follow SAP convention (6-digit codes: 740xxx = general expenses, 540xxx = raw materials, 620xxx = services).

**Why these specific items?** Each procurement item maps to a different Scope 3 category under GHG Protocol (e.g., steel = Category 1 purchased goods, freight = Category 4 upstream transport, catering = Category 6 travel indirectly). This shows the analyst the data they'd need to eventually attribute to spend-based emission factors.

### What would break in a real deployment

1. **German headers**: Our parser expects English column names (`doc_date`, `quantity`, `unit`). A German SAP system will export `Buchungsdatum`, `Menge`, `Einheit`. We'd need a column mapping table per client.

2. **Date format inconsistency**: The parser handles `DD.MM.YYYY` and ISO, but `MM/DD/YYYY` (US format) would silently mis-parse (e.g., `01/03/2024` could be Jan 3 or Mar 1).

3. **SAP unit codes**: SAP unit `M3` (cubic meter) is not in our unit normalisation table. A gas consumption export would land with an unknown unit.

4. **Reversal documents**: A negative fuel quantity will be flagged suspicious. An analyst would need to match it to the original document and exclude it — we don't automate this.

5. **Multi-currency**: If procurement amounts are in USD, GBP, and EUR in the same file, we store them as-is. Aggregation across currencies isn't meaningful without FX rates.

---

## 2. Utility (Electricity)

### What format was researched

Utility data reaches a facilities team through several channels:

1. **Utility portal CSV export** — Every major utility (E.ON, RWE/innogy, EnBW in Germany; EDF, Octopus, British Gas in UK; PG&E, ConEd in US) offers a portal where the account manager can download consumption data by meter, by billing period, as a CSV or Excel file.

2. **Green Button / ESPI (Energy Service Provider Interface)** — A US standard for sharing utility data. The utility exposes an OAuth-protected API returning XML in the ESPI schema. Adopted by many US utilities (PG&E, SDG&E, ConEd). Not widely adopted outside North America.

3. **PDF bill** — The paper bill equivalent. Contains all the information but in a format designed for humans, not machines. Requires PDF parsing (pdfplumber, PyMuPDF) or OCR.

4. **EDI 810 / 867** — ANSI X12 EDI formats used by large industrial customers in the US for utility billing. Very structured, very niche.

**We chose portal CSV export** — see DECISIONS.md D2.

### What was learned

**Key gotchas from utility exports:**

- **Billing periods ≠ calendar months**: A meter is read on the actual read date, which is not the 1st or last of the month. A "January" bill might cover Dec 28 – Jan 29. This means monthly totals can't be summed by filtering on a single date column — you need `period_start` and `period_end` to correctly attribute consumption to reporting periods.

- **Meter ID vs account number**: A single electrical account may have multiple meters (sub-meters). Each meter gets a row. The hierarchy (account → site → meter) is often not included in the export.

- **Units vary by scale**: Small office meters report in kWh. Industrial meters often report in MWh (to avoid large numbers). Some UK suppliers report in kVAh (kilovolt-ampere hours, includes reactive power). Our normalisation converts MWh to kWh.

- **Tariff structures**: UK utilities split consumption into "day rate" and "night rate" (Economy 7/10). German utilities have HT (Haupttarif / peak) and NT (Nebentarif / off-peak). A full-precision export will have separate rows for each tariff band. Our sample simplifies this to one row per meter per period with a `tariff` label.

- **Estimated vs actual reads**: When a meter reader can't access a site, the utility estimates the consumption based on historical averages. The export typically marks this with a flag column (`read_type: E vs A`). We ignore this flag in our parser — in real deployment, estimated reads should be reviewed more carefully.

### What the sample data looks like and why

`utility_sample.csv` has 12 rows across 3 calendar months for 5 meters in 4 facilities.

**MTR-DE02-PROD** (Munich production hall) has the highest consumption (~180k kWh/month) — realistic for industrial processes. **MTR-DE01-A** and **MTR-DE01-B** represent two sub-meters in the Frankfurt HQ building. One row for February uses `MWh` (195.0 MWh) instead of kWh to test the unit conversion logic. The final row (Hamburg Warehouse, March) is intentionally missing the `usage` value to exercise the failed-parse path.

### What would break in a real deployment

1. **Multiple tariff bands**: If the utility exports HT and NT rows separately for the same meter+period, we'd create two NormalizedRecords for one billing period — which would double-count when aggregating. We'd need a merge step.

2. **Estimated reads**: We treat all reads as actual. A facilities team needs to re-ingest corrected actuals when estimates are trued up.

3. **Cross-utility schema differences**: E.ON's portal export has different column names than EnBW's or Octopus's. We'd need a column mapping configuration per utility.

4. **Reactive power (kVAh)**: Our unit table doesn't include kVAh. Conversion to kWh requires a power factor, which varies by site.

5. **Solar / net metering**: Sites with on-site solar can have net negative consumption in a period (more generated than consumed). We flag negative quantities as suspicious, which would cause alert fatigue at a net-metered site.

---

## 3. Corporate Travel (Flights, Hotels, Ground Transport)

### What format was researched

Corporate travel data lives in travel management systems:

1. **SAP Concur** — Market leader (~$1.9B revenue, 25,000+ corporate clients). Exposes a REST API (`/api/v3.0/expense/reports`, `/travel/trips/v1`) with OAuth 2.0. Also provides a "standard extract" CSV download (called "Expense Extract" or "Travel Extract") via their admin portal. The standard Concur CSV has 100+ columns.

2. **Navan (formerly TripActions)** — Challenger to Concur. Has a REST API at `app.navan.com/api/v1/trips`. Also provides CSV exports of trip data. Column names differ from Concur.

3. **Egencia (Amex GBT)** — Similar to Concur. CSV export available.

4. **Manual spreadsheet** — Many SMEs track travel in an Excel sheet maintained by an executive assistant or finance team.

**We chose CSV export modeled on Concur's standard travel extract** — see DECISIONS.md D3.

### What was learned

**Key gotchas from corporate travel data:**

- **Airport codes vs city names**: Concur stores the booking with IATA airport codes (FRA, JFK, LHR). Some systems store city names or full airport names. IATA codes are the right identifier for computing flight distances; city names require geocoding.

- **Distance is often absent**: The travel platform records the booking cost and route, but not the distance. Distance must be inferred from IATA code pairs using a great-circle calculator (haversine formula) or a lookup table. Different platforms use different distance calculation methodologies, which affects the emission factor applied.

- **Multi-leg flights look like one booking**: A trip `FRA → AMS → JFK` may appear as one booking with one cost. The individual legs (FRA→AMS, AMS→JFK) have different distances and emission profiles. We treat the booking as a single record with origin=FRA and destination=JFK.

- **Hotel nights**: Hotels don't have an "origin" or "destination" — they have a check-in date, checkout date, and a city. The relevant quantity for emissions is the number of nights multiplied by a per-night emission factor. We store nights as `quantity` with unit "nights" (implicitly, in metadata).

- **Ground transport categories**: Taxi, rental car, and train have very different emission factors. Our `ground` activity type collapses all of these. The `vendor` field preserves the actual provider.

- **Ticket class matters for flights**: Economy, Premium Economy, Business, First class flights have different cabin multipliers in DEFRA/BEIS emission factors (Business class can be 3-4x economy per km). We store `ticket_class` in `metadata`.

### What the sample data looks like and why

`travel_sample.csv` has 15 rows covering Q1 2024 across 3 business trips:

**NYC Strategy Summit (Jan)**: Two employees flying FRA→JFK (one Business, one Economy), hotel stays (3 and 2 nights), ground transport in NY. This tests Business vs Economy ticket class distinction.

**London client meeting (Jan)**: One employee MUC→LHR with missing distance — intentionally triggers the `missing_distance` suspicious flag and `missing_airports` won't trigger since we have origin/destination. Tests the suspicious detection path.

**Dubai MENA conference (Feb)**: Two employees HAM→DXB with contrasting ticket classes (Economy vs Business). 4-night hotel stays.

**Paris supplier audit (Feb)**: One short-haul CDG trip, ground transport, no hotel (day trip).

**Singapore summit (Mar)**: One Business class FRA→SIN with missing distance — second intentional missing-distance case.

### What would break in a real deployment

1. **Distance inference**: We rely on the travel platform providing distance. Most don't for hotel/ground. We'd need an IATA→coordinate lookup table and haversine computation.

2. **Concur's actual column names**: The real Concur standard extract uses columns like `LegOriginAirportCode`, `LegDestinationAirportCode`, `PolicyTravelClassCode`. Our parser uses simplified names. A mapping layer would be needed.

3. **Multi-leg trips**: A connecting flight appears as one booking but has two legs with different distances and fuel burn profiles. Without leg-level data, the emission estimate is less accurate.

4. **Personal bookings outside the platform**: Employees who book travel on personal cards and expense-claim later may not appear in the platform export. This is a data completeness issue, not a parsing issue.

5. **Currency**: Our sample uses EUR throughout. A global travel program will have USD, GBP, SGD, AED expenses in the same export. Currency normalisation for spend-based allocation would require FX rates.
