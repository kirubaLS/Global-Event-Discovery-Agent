# US Export Entry Agent — Technical Specification

**Working name:** Export-to-US Agent (internal: `us-entry-agent`)
**Positioning line:** *Anything that ships into the United States starts here.*
**Status:** Specification / pre-build. No code written yet.
**Relationship to this repo:** the Global Event Discovery Agent is the reference
architecture. This document describes the second product built on the same
machine — same FastAPI + grounded-LLM + strict-JSON + gated-PDF pipeline, a
different domain and a different failure model.

---

## 1. The pitch

### 1.1 The one-liner

An exporter anywhere in the world types *what* they make, *what it is made of*,
*where it is made*, and *what a shipment is worth*. In ninety seconds they get a
**US Entry Readiness Report**: the likely HTS classification, the full duty stack
that actually applies today, the landed cost per unit, every US agency that has
to clear the goods, the exact document set for entry, and a GO / GO WITH
CONDITIONS / STOP verdict — every number carrying a source URL and an
as-of date.

### 1.2 Why this, why now

The US import rulebook has been rewritten faster in the last two years than in
the previous thirty. Country-specific IEEPA tariffs, Section 232 expansions into
steel, aluminium, copper, autos and downstream derivative parts, the end of the
$800 de minimis exemption, tariff **stacking** rules that decide which measures
add and which absorb, aggressive UFLPA detention, widening AD/CVD scope rulings —
and, on top of all of it, live litigation that can retroactively unwind
whole tariff programs.

Three consequences, and they are the whole business case:

1. **Every exporter's landed-cost spreadsheet is stale.** The rate they quoted
   their US buyer last quarter may be wrong by double digits this quarter.
2. **Every general-purpose LLM is confidently wrong on this.** A frozen-weights
   model answers a duty question from training data that predates the current
   rate. It sounds authoritative and it costs the user real money. This is not a
   flaw to work around — it is the exact gap the product fills.
3. **The incumbent answer is a phone call to a customs broker**, which is slow,
   costs money before you know whether the deal is even viable, and does not
   scale to "I want to price 40 SKUs."

So the product is not "an LLM that knows tariffs." It is **a research agent that
refuses to answer from memory**, verifies every rate against a primary source on
each run, timestamps it, and shows the receipts. The discipline *is* the moat.

### 1.3 Why it is a better business than the events agent

| | Event Discovery Agent | Export-to-US Agent |
|---|---|---|
| Question the user is asking | "Where should I spend marketing budget?" | "Will this shipment clear, and what does it cost me?" |
| Urgency | Planning-cycle, quarterly | Deal-blocking, this week |
| Value of a right answer | A better booth decision | Duty on a $250k shipment; a detained container |
| Cost of a wrong answer to the user | Wasted trip | Penalties, demurrage, seizure, a dead US buyer |
| Repeat frequency | 1–2× a year | Per SKU, per origin change, per rule change |
| Natural channel | Direct to marketing | Freight forwarders, 3PLs, customs brokers, export promotion councils, chambers of commerce |
| Willingness to pay | Marketing-budget soft | Landed-cost line item, hard ROI |

Same funnel mechanics you already run (work-email gate → OTP → report → PDF by
email → lead in Postgres), but the lead is a company with an actual shipment and
a deadline, and the report is a document they forward internally.

### 1.4 The three revenue turns

1. **Self-serve report.** Free tier = 3 runs/day (identical to the current
   rate-limit design). Paid = unlimited runs, multi-SKU batch, no gate.
2. **Broker / forwarder white-label.** The report is the top of a customs
   broker's funnel. They embed it, we take a seat fee. The report's own
   escalation path — "this classification is advisory; here is how to get a
   binding CBP ruling" — is a warm handoff, and a referral line.
3. **Rate-change monitoring (the recurring revenue).** Once a user has run an
   HTS code + origin pair, we hold a `duty_snapshot`. Re-run it weekly, diff it,
   and email the user when their number moves. This is a subscription, and the
   database that makes it possible is a byproduct of serving free reports. Every
   free run makes the paid product better and cheaper.

### 1.5 The compounding asset

Two-level caching (§5.3) means classification results are reused across users
forever and duty stacks are reused within a freshness window. After N thousand
runs you own a growing, source-cited table of *(HTS code × country of origin ×
date → effective duty stack)*. That table is:

- a cost reduction (cache hits cost nothing),
- a latency reduction (instant answers on popular lanes),
- the monitoring product's data source,
- and, eventually, sellable data in its own right.

The events agent's cache expires into nothing. This one accumulates.

---

## 2. Scope

### 2.1 In scope (v1)

Goods physically imported into the United States for commercial sale, by an
exporter/manufacturer outside the US who is trying to price and de-risk the
shipment before committing.

### 2.2 Out of scope (v1) — say so explicitly in the UI

- Services, software delivered electronically, digital goods.
- Personal / non-commercial shipments.
- US **export** controls on goods leaving the US (EAR/ITAR licensing) — flagged
  as a risk, never adjudicated.
- Binding classification. The report is advisory. It never claims to be a CBP
  ruling and always names the path to one.
- Actual filing. We do not file ISF or entries. We tell you what is required.

### 2.3 The hard non-goal

**The agent never gives a single confident number it cannot source.** An
unverifiable rate is `null` with a stated reason, never `0` and never a guess.
This mirrors `est_attendees → 0` in `gpt_search.py` but is stricter, because here
a fabricated number is a financial injury rather than a bad recommendation.

---

## 3. The user flow

```
Landing → Product form → work-email + OTP gate → queued research job
        → live progress → Entry Readiness Report → deep dive per section
        → email PDF → (paid) monitoring opt-in
```

Deliberately identical in shape to the current app so the entire frontend shell,
the OTP flow, the job-polling flow, the maintenance gate and the PDF mailer are
reused rather than rebuilt.

### 3.1 Input (the "ICP form" analog)

| Field | Type | Required | Notes |
|---|---|---|---|
| `product_description` | free text | yes | The source of truth, exactly like `buyer_description`. Let the model read the wording; do not pre-parse with keyword tables. |
| `materials` | free text | yes | Composition drives HTS chapter more than function does. "Ceramic mug with a silicone base" is two chapters' worth of argument. |
| `intended_use` | free text | no | Disambiguates GRI 3 ties (a "cutting tool" for surgery vs. for wood). |
| `country_of_manufacture` | select | yes | HARD input. Drives Section 301/232/IEEPA, AD/CVD, UFLPA and FTA eligibility. |
| `country_of_shipment` | select | no | Defaults to manufacture. Transshipment is a red flag the report must raise. |
| `unit_value_usd` | number | yes | Per-unit customs value. |
| `units_per_shipment` | number | yes | |
| `annual_units` | number | no | Sizes the exposure and the upsell. |
| `incoterm` | select | no | EXW/FOB/CIF/DDP — determines who is Importer of Record and whether freight is dutiable. |
| `transport_mode` | select | no | Ocean vs. air changes ISF applicability, HMF, and timelines. |
| `hs_code_guess` | text | no | If they already have a 6-digit HS from their own country, use it as a prior, never as the answer. |
| `end_customer_type` | select | no | Distributor / retailer / direct-to-consumer. DTC changes PGA and labeling exposure. |
| `email` | work email | yes | Same `work_email.py` validation + OTP as today. |

A live `/api/parse-product` endpoint mirrors `/api/parse-icp`: a small, fast model
(`gpt-4.1-nano`, no web search, hard `max_output_tokens` cap) turns the free text
into chips — likely chapter, likely material class, likely PGA — so the form feels
alive while the user types. Cached in Redis by text hash. Falls back to
`{"source":"rules"}` on any failure so the form can never break.

### 3.2 Output — the US Entry Readiness Report

Eight sections. Each is a card in the UI and a page in the PDF.

1. **Classification.** Top 3 candidate HTS codes, each with a confidence, the
   GRI reasoning in plain English, the chapter/section notes relied on, and any
   CROSS ruling found for a comparable article. The chosen one is marked; the
   alternatives are shown *because the alternative is often cheaper and the user
   deserves to see the argument.*
2. **Duty stack.** Every component that applies, as separate lines: Column 1
   General (MFN), preferential rate if an FTA applies, Section 301, Section 232,
   IEEPA / country-specific measures, AD/CVD if the goods fall in scope, plus
   MPF and HMF. Each line: rate, basis, legal citation, source URL, as-of date.
   The stacking order is stated, not assumed.
3. **Landed cost.** Computed **in Python, never by the model** (§5.4). Per unit
   and per shipment, shown as a range with the assumptions listed.
4. **Agency requirements (PGA).** Which of FDA, USDA/APHIS, FSIS, EPA, FCC,
   CPSC, DOT/NHTSA, TTB, FWS, CBP-only apply, and what each one needs
   (registration, prior notice, permits, certificates, testing).
5. **Documents & filings.** Commercial invoice requirements, packing list,
   BOL/AWB, ISF 10+2 timing, customs bond type and sizing, entry summary,
   certificate of origin, any PGA-specific filing.
6. **Origin, marking and FTA.** Country-of-origin determination, substantial
   transformation questions the user must answer, marking rules for the article
   and its retail packaging, and whether a preference program plausibly applies.
7. **Risk flags.** UFLPA / forced-labour exposure, AD/CVD scope risk,
   transshipment risk, IPR and trademark recordation, dual-use, restricted
   parties, licensing.
8. **Verdict.** `GO` / `GO_WITH_CONDITIONS` / `STOP`, a readiness score 0–100, the
   three things to fix first, and — the section that sells the product — a
   **sourcing comparison**: the same duty stack recomputed for 2–3 alternate
   countries of manufacture, so the user sees "moving this to Vietnam saves
   $18.40/unit" in a number.

---

## 4. The anti-hallucination doctrine

This section is the product. Treat every rule as a hard requirement on the
prompt, the validator, and the UI.

1. **No rate from memory, ever.** Every duty rate, threshold, exclusion and
   agency requirement must be found on this run, on a primary source, via web
   search. The model is explicitly told its training data is out of date on this
   subject and must be distrusted.
2. **Source hierarchy.** Accept, in order: `hts.usitc.gov` (the HTSUS itself) ·
   `federalregister.gov` · `cbp.gov` and CSMS messages · `rulings.cbp.gov`
   (CROSS) · `trade.gov` / `access.trade.gov` (AD/CVD orders) · the specific PGA's
   own `.gov` site. Reject as a citation: freight-forwarder blogs, news
   aggregators, LLM-generated summary sites, undated marketing pages.
3. **Every number carries `source_url` + `as_of`.** A component without both is
   dropped by the validator before it reaches the user.
4. **Unknown is `null`, not `0`.** And `null` renders in the UI as "not
   verified — here is why," never as a blank or a zero.
5. **Volatility warning is mandatory.** Any component whose source is dated
   within the last 180 days, or that belongs to a program under active
   litigation, is flagged `volatile: true` and rendered with a "re-check before
   you ship" badge.
6. **Advisory, not binding — stated on every surface.** Report header, PDF
   footer, API response field. Always paired with the escalation path (CBP
   binding ruling via eRulings / CROSS, or a licensed customs broker).
7. **The model never does arithmetic.** It returns rate *components*; Python
   multiplies. See §5.4.
8. **Search budget is a hard cap** (start at 10 searches; the events agent uses
   6). Over budget → return what is verified, mark the rest `null`, and say so in
   `research_notes`. An honest partial report beats a padded one — the same rule
   that governs "fewer than 6 events" today.

---

## 5. Architecture

### 5.1 Shape (unchanged from this repo)

```
frontend (React + Vite, static)
      │  POST /api/export-check   → { status:"queued", job_id }
      │  GET  /api/export-check/status/{job_id}  (poll)
      ▼
FastAPI (single Render instance)
      ├── api/routes_export.py    ← job orchestration, gates, rate limit
      ├── api/routes_email.py     ← reused as-is (PDF + Resend)
      ├── classifier.py           ← Stage A: product text → HTS candidates
      ├── duty_research.py        ← Stage B: HTS × origin → duty stack + PGA
      ├── landed_cost.py          ← pure Python arithmetic, no LLM
      ├── validators.py           ← drops anything unsourced (the gatekeeper)
      ├── cache.py                ← two-tier Redis cache + daily limit
      ├── db.py                   ← Neon Postgres, fire-and-forget
      └── config.py               ← pydantic-settings, same optional-everything rule
```

Every external dependency stays optional and degrades silently, exactly as
`cache.py` and `db.py` do today: no Redis → no cache, no limits; no Postgres →
nothing stored; no OTP sender → the gate self-disables rather than locking users
out. Never let infrastructure break a report.

### 5.2 The two-stage pipeline — the one real architectural change

The events agent is one LLM call. This one is deliberately two, because the two
halves have completely different cache lifetimes and different failure modes.

**Stage A — Classification.** Input: product text, materials, use. Output: 3
candidate HTS codes with GRI reasoning. Depends only on the *product*. A ceramic
mug is a ceramic mug in perpetuity. Search budget: 4 (HTSUS chapter/heading text
+ CROSS rulings for comparable articles). **Cache TTL: 90 days**, keyed by a
normalised product fingerprint — so it is shared across every user who describes
the same thing.

**Stage B — Duty & compliance.** Input: the chosen HTS code + country of origin +
today. Output: the duty stack, PGA list, document set, risk flags. Depends on the
*rulebook*, which moves weekly. Search budget: 6. **Cache TTL: 24 hours**, keyed
by `(hts10, origin, utc_date)`.

Consequences worth stating out loud:

- Stage B is reused across *products* — everyone importing under the same
  heading from the same country gets the same stack. Hit rates climb steeply.
- A user changing only shipment value or quantity re-runs **neither** stage;
  `/api/landed-cost` recomputes in Python in milliseconds. The events agent has
  no equivalent of this and it makes the UI feel like a calculator rather than a
  slot machine.
- The sourcing comparison (§3.2.8) is just Stage B run for 2–3 more origins,
  usually served from cache. A headline feature for near-zero marginal cost.
- If Stage A is wrong, Stage B is confidently wrong about the wrong product.
  Hence: always show the alternate classifications, always show the reasoning,
  never hide the fork.

### 5.3 Caching and cost

| Layer | Key | TTL | Why |
|---|---|---|---|
| Product parse (form chips) | `sha256(text)` | 7 d | Debounced typing hammers the same strings. Already the pattern in `/api/parse-icp`. |
| Stage A classification | `sha256(desc + materials + use, normalised)` | 90 d | Product facts do not change. |
| Stage B duty stack | `hts10 : origin : YYYY-MM-DD` | 24 h | Rules do change — daily granularity is the honest ceiling. |
| Full report | `sha256(whole form)` | 24 h | Exact resubmit (post-OTP, or the auto-resubmit path) must not cost a second run — and, as today, must **refund** the rate-limit slot it just consumed. |
| Rate limit | `device_id` and `ip` | UTC day | 3/day free, both counted independently, Postgres fallback when Redis is down. |

Rough per-run economics: a cold run is two grounded reasoning calls with ~10
searches. A warm run (Stage A hit + Stage B hit) is arithmetic only and costs
nothing. Model the business on a 60–75% blended hit rate once a few thousand
lanes are covered; popular lanes (China→US electronics, India→US textiles,
Vietnam→US furniture) saturate first.

### 5.4 Deterministic arithmetic (`landed_cost.py`)

The model returns components. Python computes. Non-negotiable, because an LLM
that multiplies is an LLM that silently mis-multiplies, and this number goes into
someone's quote.

```python
# Illustrative shape — rates arrive as validated components, never as a total.
customs_value = unit_value * units          # per the incoterm; state the basis
duties = sum(c.rate * customs_value for c in ad_valorem_components)
duties += sum(c.amount * units for c in specific_components)   # e.g. cents/kg
mpf  = clamp(customs_value * MPF_RATE, MPF_MIN, MPF_MAX)       # rates: verified, not hardcoded
hmf  = customs_value * HMF_RATE if ocean else 0
landed = customs_value + duties + mpf + hmf + freight + insurance + brokerage
```

Every constant in that block is a **verified, sourced, dated value from Stage B**,
not a literal in the source file. If a constant could not be verified this run,
the line renders as "not verified" and is excluded from the total, and the total
is labelled a **partial**.

Output is always a **range with stated assumptions**, never a single confident
figure — because freight, insurance and brokerage are user-supplied estimates and
the report must not launder an estimate into a fact.

### 5.5 Job orchestration

Copy `routes_search.py` verbatim in structure: cache check first (and refund the
rate-limit slot on a hit), else create a `job_id`, `asyncio.create_task` the work,
return `{"status":"queued","job_id":...}`, and mirror job state into Redis with a
short TTL so a poll survives an instance blip. A synchronous two-minute request
is fragile behind a proxy; the queued pattern already solved that here.

Add one thing the events agent lacks: **staged progress**. The job record carries
`stage: "classifying" | "researching_duties" | "checking_agencies" | "composing"`
so the UI shows real movement across a 90-second wait instead of a spinner. The
existing `PipelineMachine.jsx` component is already built for exactly this.

---

## 6. Data model (Neon Postgres — all optional, all fire-and-forget)

```
export_submissions
  id uuid pk · created_at · email · ip · device_id · session_id
  payload jsonb            -- the raw form, source of truth
  country_of_manufacture · unit_value_usd · units_per_shipment

classifications
  id uuid pk · product_fingerprint text idx · created_at
  candidates jsonb         -- [{hts10, confidence, reasoning, citations}]
  chosen_hts10 text

duty_snapshots            -- THE ASSET. Never overwritten; append-only.
  id uuid pk · hts10 · origin_country · captured_at
  components jsonb         -- [{kind, rate, basis, citation, source_url, as_of}]
  volatile bool · research_notes text
  unique (hts10, origin_country, captured_at::date)

reports
  id uuid pk · submission_id fk · created_at
  report jsonb · verdict · readiness_score · partial bool

watches                   -- the monitoring subscription
  id uuid pk · email · hts10 · origin_country · created_at · active bool
  last_notified_at · last_seen_snapshot_id fk

consent_log               -- reused as-is
```

`duty_snapshots` being append-only is what makes §1.4.3 possible: the weekly
monitoring job re-runs Stage B for every distinct `(hts10, origin)` in `watches`,
diffs against the last snapshot, and emails on change. The diff is free; the data
was collected serving free users.

---

## 7. API surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/parse-product` | Live form chips. Nano model, no search, hard token cap, 7-day cache, rules fallback. |
| `POST` | `/api/classify` | Stage A alone. Fast path for "just tell me my HTS code." A cheap free hook. |
| `POST` | `/api/export-check` | Full run. Returns `{status:"done", result}` on cache hit, else `{status:"queued", job_id}`. |
| `GET` | `/api/export-check/status/{job_id}` | Poll. Returns `stage` for the progress UI. |
| `POST` | `/api/landed-cost` | Pure arithmetic. No LLM, no cost. Instant recompute when value/qty/freight change. |
| `POST` | `/api/compare-origins` | Stage B for N alternate origins. Mostly cache hits. |
| `POST` | `/api/email-report` | Reuse `routes_email.py` unchanged; swap the PDF template. |
| `POST` | `/api/watch` | Create a rate-change watch (paid). |
| `GET` | `/api/health`, `/api/maintenance-status` | Reuse. |
| — | OTP + email validation + analytics + consent | Reuse `routes_search.py` endpoints verbatim. |

### 7.1 Response contract (abridged)

```jsonc
{
  "report_id": "uuid",
  "generated_at": "2026-09-01T10:22:31Z",
  "partial": false,                    // true if any component was unverifiable
  "product": { "description": "", "materials": "", "origin": "IN" },

  "classification": {
    "chosen": {
      "hts10": "6912.00.4810",
      "description": "",               // official HTSUS article description
      "confidence": "high",            // high | medium | low
      "reasoning": "",                 // GRI logic in plain English
      "citations": [{ "title": "", "source_url": "", "as_of": "2026-08-30" }]
    },
    "alternatives": [ /* same shape, 2 items — always shown, never hidden */ ]
  },

  "duty_stack": {
    "components": [
      {
        "kind": "mfn",                 // mfn|fta|section_301|section_232|ieepa|addcvd|mpf|hmf|other
        "label": "",
        "rate_type": "ad_valorem",     // ad_valorem | specific | compound
        "rate": 0.095,                 // null when unverified — NEVER 0 as a guess
        "amount_per_unit_usd": null,
        "basis": "customs_value",
        "legal_citation": "",
        "source_url": "",
        "as_of": "2026-08-30",
        "volatile": true,
        "note": ""
      }
    ],
    "stacking_order": ["mfn", "section_301", "section_232", "ieepa"],
    "effective_rate": 0.345,           // computed in Python from the above
    "unverified_components": []        // named, so the UI can say what is missing
  },

  "landed_cost": {
    "currency": "USD",
    "customs_value": 0, "duties": 0, "fees": 0,
    "user_estimates": { "freight": 0, "insurance": 0, "brokerage": 0 },
    "per_unit_low": 0, "per_unit_high": 0,
    "assumptions": [""], "partial": false
  },

  "agencies": [
    { "agency": "FDA", "applies": "likely", "why": "",
      "requirements": [""], "source_url": "", "as_of": "" }
  ],

  "documents": [
    { "document": "ISF 10+2", "required": true, "when": "24h before lading",
      "who_files": "importer/agent", "notes": "", "source_url": "" }
  ],

  "origin_and_marking": { "determination": "", "fta_candidates": [],
                          "marking_requirements": [""], "open_questions": [""] },

  "risk_flags": [
    { "flag": "UFLPA", "severity": "high", "why": "",
      "mitigation": "", "source_url": "" }
  ],

  "verdict": {
    "decision": "GO_WITH_CONDITIONS",
    "readiness_score": 68,
    "top_actions": ["", "", ""],
    "rationale": ""
  },

  "origin_comparison": [
    { "origin": "VN", "effective_rate": 0.12, "per_unit_delta_usd": -18.40,
      "caveats": [""] }
  ],

  "research_notes": "",                // honesty field: gaps, budget spent, caveats
  "disclaimer": "Advisory only. Not a binding CBP classification ruling…"
}
```

### 7.2 Validation (`validators.py`) — the gatekeeper

Mirrors `_validate_events()`, stricter. Runs on every model reply, before the
user sees anything:

- Drop any duty component missing `source_url` **or** `as_of`.
- Drop any `source_url` not on the §4.2 allowlist of primary-source hosts
  (same mechanism as `_BAD_URL_HOSTS`, inverted to an allowlist because the cost
  of a bad citation is higher here).
- Reject `as_of` dates in the future; flag any older than 365 days as stale.
- HTS codes must be 10 digits, digits-only after normalising dots; 6- or 8-digit
  replies are accepted but downgraded to `confidence: "low"` and surfaced as
  "needs a broker to complete the statistical suffix."
- Any dropped component's `kind` is appended to `unverified_components`, and
  `partial` is set — a component silently vanishing is the one failure mode that
  would make this product dangerous.
- Recompute `effective_rate` and every currency figure in Python from surviving
  components. Whatever total the model volunteered is discarded unconditionally.

---

## 8. Prompt design

Two prompts, kept in sync with `GPT_EXPORT_TO_US_TEMPLATE.md` at the repo root
(the same convention `GPT_EVENT_SEARCH_TEMPLATE.md` follows today).

**Stage A** casts the model as a customs classification analyst: apply the
General Rules of Interpretation in order, reason from material and function,
consult HTSUS chapter and section notes, look for CROSS rulings on comparable
articles, and return three ranked candidates with the argument for each. It is
told explicitly that being *usefully uncertain* — showing the fork between two
headings — beats a confident single answer.

**Stage B** casts the model as a trade-compliance researcher with one standing
instruction above all others: **your training data is out of date on this subject
and must not be used.** Every rate is found this run, on a primary source, or it
is `null`. It returns components, never totals; citations, never summaries; and
it states in `research_notes` exactly what it could not verify and why.

Full text lives in the template file.

---

## 9. Frontend reuse map

| Existing component | Becomes |
|---|---|
| `ICPForm.jsx` | `ProductForm.jsx` — same OTP flow, same debounced parse chips, same validation |
| `PipelineMachine.jsx` | Staged progress across classify → duties → agencies → compose |
| `ShowRankingPage.jsx` | `DutyStackPage.jsx` — components as rows instead of events |
| `ShowDeepDivePage.jsx` | `SectionDeepDivePage.jsx` — one section per card with citations |
| `EmailReportModal.jsx` | Unchanged |
| `MeetingPotentialCard.jsx` | `LandedCostCard.jsx` — the hero number, with the live recompute |
| `HeroGlobe.jsx` | Origin → US trade-lane arc |
| Legal/FAQ/Pricing/Privacy | Unchanged shells, new copy |
| `client.js` | New endpoints, same fetch wrapper, session/device headers, error handling |

The frontend is roughly a re-skin. That is the point of building the second
product on the first product's chassis.

---

## 10. Build plan

**Phase 0 — Spike (3–5 days).** No UI. A script: form payload in, Stage A + Stage
B + validators + landed cost, JSON out. Run it on 20 real product/origin pairs
you can check by hand. **The only question that matters: what fraction of duty
components come back with a valid primary-source citation?** If it is below ~80%,
the prompt and source hierarchy need work before anything else gets built.

**Phase 1 — MVP (2–3 weeks).** Backend endpoints, Redis two-tier cache, Postgres
tables, job + polling, form, report page, PDF. Ship behind the same 3/day +
work-email gate.

**Phase 2 — Depth (3–4 weeks).** Origin comparison, `/api/classify` free hook,
multi-SKU batch upload (CSV in, report out), broker referral handoff.

**Phase 3 — Recurring (4+ weeks).** Watches, weekly diff job, change alerts,
paid tier, white-label embed for forwarders.

**Phase 4 — Data.** Direct HTSUS ingest to replace search for the base MFN rate
(the one component that *is* bulk-downloadable and stable), keeping search for
everything layered on top. Cheaper, faster, and more accurate on the base layer.

---

## 11. Risks and honest limits

| Risk | Reality | Mitigation |
|---|---|---|
| **Rate volatility** | The answer can be wrong within a week of being right. | `as_of` on everything, `volatile` badges, 24h Stage B TTL, monitoring as the paid fix. |
| **Litigation reversal** | Whole tariff programs can be struck down or reinstated retroactively. | Flag programs under challenge in `risk_flags`; never present a duty as settled law; the append-only snapshot table makes retroactive re-analysis possible. |
| **Classification liability** | A wrong HTS code has legal consequences for the importer. | Advisory framing everywhere, alternatives always shown, binding-ruling path always named, no claim of professional advice. Get this reviewed by counsel before launch. |
| **Thin sourcing on obscure goods** | Some niche articles have almost no public secondary material. | Partial reports are a first-class output, not a failure. Say what is missing. |
| **Search quality** | The agent is only as good as what it finds on the run. | Primary-source allowlist, per-stage budgets, drop-not-guess validators. |
| **Users treat it as a broker** | They will. | Disclaimer on every surface including the PDF; broker referral as the designed exit. |
| **Model cost on cold lanes** | Two grounded reasoning calls is not cheap. | Two-tier cache, daily free cap, cache-hit refunds — all already proven in this repo. |

The uncomfortable one, stated plainly: **this product's core claim is accuracy,
in a domain where accuracy decays weekly.** Every design decision above —
citations, timestamps, `null` over zero, partial reports, Python arithmetic,
append-only snapshots — exists to make that claim survivable. If any of them get
traded away for a cleaner-looking report, the product becomes a liability rather
than a service.

---

## 12. Open questions for you

1. **Who is the buyer** — the exporter abroad, or the US importer of record? The
   report is the same document; the funnel, pricing and channel are not.
2. **Which lanes first?** Narrowing v1 to 2–3 origin countries and 3–4 product
   categories would let you hand-verify the output and build the cache where it
   pays off fastest.
3. **Same domain or separate brand?** Shared infra either way, but "LeadStrategus
   event intelligence" and "US customs readiness" are different trust stories.
4. **Broker partner before or after launch?** Having one lined up turns the
   disclaimer from a limitation into a feature.
