# MGC Task Pack — Parts 1–4

Deterministic, keyless Q&A over the three MGC documents. No API keys, no LLM,
no network. A salesperson types a question in plain language; the assistant
returns a grounded answer with the source shown.

## How to run

| Part | Command | What it does |
|---|---|---|
| 1 — Document Q&A | `python -m mgc.cli` | Interactive Q&A over the 3 docs |
| 1 — Verify hard cases | `python -m mgc.tests.test_hard_cases` | Runs the 5 brief test cases |
| 2 — Schema & queries | `python -m mgc.tests.verify_schema` | Loads CSV into SQLite, runs both queries |
| 3 — ML model | `python -m mgc.model` | Trains baseline model, reports recall |
| 4 — Web interface | `python -m mgc.webapp` | Opens http://localhost:8000 with both tools |
| Inspect index | `python -m mgc.tests.inspect_index` | Shows all passages, topics, TF-IDF scores |

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

## Project structure

```
mgc/
├── assistant/              # Part 1: Document Q&A engine
│   ├── docs_index.py       #   Parser + TF-IDF index
│   └── answer_engine.py    #   Intents, pricing math, refusals, conflicts
├── models/                 # Part 3: ML scorer
│   └── scorer.py           #   Logistic regression baseline
├── web/                    # Part 4: Web app
│   ├── app.py              #   FastAPI routes + API endpoints
│   └── templates/
│       └── index.html      #   Single-page UI (Q&A + lead scoring)
├── sql/                    # Part 2: SQL
│   ├── schema.sql          #   Table definition + unique constraint
│   └── queries.sql         #   Conversion rate + duplicate detection
├── data/                   # Source data
│   ├── leads.csv           #   ~9,000 historical leads
│   └── docs/               #   3 MGC markdown documents
├── tests/                  # All tests
│   ├── test_hard_cases.py  #   Part 1: 5/5 brief cases
│   ├── test_webapp.py      #   Part 4: endpoint smoke tests
│   └── verify_schema.py    #   Part 2: run queries against SQLite
├── cli.py                  # Part 1 entry point
├── model.py                # Part 3 entry point
└── webapp.py               # Part 4 entry point
```

---

## Part 1 — Document Q&A

The engine classifies each query into one of these paths, in order:

1. **Pricing math** — query mentions a unit type + a price verb. Looks up the
   base price table, applies cumulative location premiums (floor band, corner,
   Margalla-facing) exactly as the price list describes, and shows the full
   breakdown. Cash / 50% / RDA discounts are shown when mentioned.

2. **Refusal** — rental yield, anchor tenant, loan mark-up, gas timeline.
   Quoting the actual document text so the salesperson can hand it to the
   customer verbatim.

3. **Conflict detection** — the transfer fee: the price list says 2%, the
   booking policy says 2.5%. Both are shown with both sources.

4. **Topic resolution** — payment plans, discounts, other charges, booking
   process, cancellation, possession, etc. Returns the relevant passage(s)
   with source.

5. **Fallback retrieval** — TF-IDF over passage tokens; returns the closest
   passages when no specific path fires, with an honest "I can't give a
   confident answer."

### How to explain the five hard cases

| Question | What happens |
|---|---|
| Base price of a 2-bed in Block B | Direct lookup: PKR 22,425,000. Source shown. |
| Margalla-facing corner, floor 15, 2-bed Block B | Base 26,855,000 + 4% + 3% + 6% = 30,346,150. Full breakdown. |
| Transfer fee | Conflict surfaced: 2% (price list) vs 2.5% (booking policy). Both shown. |
| Rental yield on a 1-bed | Refused. FAQ verbatim: "MGC does not publish rental yield projections." |
| Anchor tenant | Refused. Brochure verbatim: "no anchor tenant has been confirmed." |

### Why no LLM?

The brief's hard cases test exactly what LLMs get wrong: refusals, conflicts,
and precise arithmetic. This engine never generates text beyond the documents'
own words for refusals/conflicts, and computes pricing from a fixed table.

---

## Part 2 — Database

### Schema (`sql/schema.sql`)

One `leads` table. Defended as minimal: one row per lead. The
`crm_record_hash` column uniquely identifies a person — if the same lead is
entered twice by different agents, the UNIQUE constraint rejects the second
insert. In production you'd UPSERT instead, but the constraint is the hard
backstop.

Key design choices:
- `lead_id` is the primary key (unique per CRM row).
- `crm_record_hash` gets a **UNIQUE constraint** — the hard backstop against
  duplicate leads. Same person entered twice → second INSERT fails.
- Indexes on `source` and `converted` for the query patterns below.

### Queries (`sql/queries.sql`)

**Q1 — Conversion rate by source (200+ leads):**

| Source | Leads | Converted | Rate |
|---|---|---|---|
| Referral | 730 | 95 | 13.01% |
| Walk-in | 610 | 63 | 10.33% |
| Facebook Ads | 2,366 | 160 | 6.76% |
| Google Search | 1,460 | 96 | 6.58% |
| WhatsApp Campaign | 548 | 35 | 6.39% |
| Property Portal | 1,812 | 108 | 5.96% |
| Instagram | 1,007 | 55 | 5.46% |
| Billboard | 282 | 12 | 4.26% |
| Expo Stall | 345 | 10 | 2.90% |

**Q2 — Duplicate leads:** 160 hashes appear more than once (320 rows total).
Prevention: UNIQUE constraint on `crm_record_hash`.

---

## Part 3 — ML

### Data cleaning decisions

**Dropped (post-creation / leaky):**
- `lead_id`, `crm_record_hash` — identifiers, not features.
- `calls_made`, `total_call_seconds`, `whatsapp_replies`, `site_visits` —
  actions taken after lead creation. Using them = data leakage.
- `token_amount_received_pkr` — essentially the outcome. Circular.

**Dropped (high null / low signal):**
- `bedrooms` — 39.3% null. `property_type` already captures the distinction.
- `area` — 5.2% null, high cardinality.

**Kept:**
- `source`, `city`, `property_type` — one-hot encoded.
- `budget_pkr_lac`, `agent_experience_years`, `first_response_minutes` —
  numeric, median-imputed.
- `is_overseas`, `referred_by_existing_client`, `has_financing_approved` —
  boolean flags.

### Metric: Recall

6.9% conversion rate → accuracy is meaningless (always-predict-no = 93.1%).
Recall catches as many real converts as possible; false positives are cheap.

### Results

| Metric | Logistic Regression | Random Forest |
|---|---|---|
| Accuracy | 67.8% | 71.9% |
| Precision | 13.7% | 13.7% |
| **Recall** | **68.0%** | 57.0% |
| F1 | 22.8% | 22.1% |
| AUC-ROC | 0.742 | 0.724 |

Logistic Regression chosen: better recall (68% vs 57%) and AUC (0.742 vs 0.724).
The linear model + balanced class weights handles the 6.9% minority better than
trees, which tend to predict the majority class.

---

## Part 4 — Web Interface

Single page with two tools:

**Document Q&A** — type a question, get a grounded answer with sources.
Status badge: green (answered), yellow (conflict), red (refused).

**Lead Scoring** — fill in source, city, property type, budget, agent
experience, response time, and boolean flags. Returns a conversion probability
from the Part 3 model, retrained on the full dataset at startup.

### API endpoints

| Endpoint | Method | Body | Returns |
|---|---|---|---|
| `/` | GET | — | HTML page |
| `/api/ask` | POST | `{"question": "..."}` | `{answer, sources, status}` |
| `/api/score` | POST | Lead JSON | `{probability, label}` |
