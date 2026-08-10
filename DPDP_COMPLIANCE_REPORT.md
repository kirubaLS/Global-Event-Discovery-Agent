# DPDP Act 2023 — Safeguarding Report for LeadStrategus

**Scope:** LeadStrategus.com — B2B lead generation, database-as-a-service, intent intelligence, event ABM (including this Global Event Discovery Agent product).
**Law:** Digital Personal Data Protection Act, 2023 (India) + Draft DPDP Rules, 2025.
**Status:** DRAFT — do not merge until approved.

---

## Executive Summary: The Core Threat

LeadStrategus operates as a **Data Fiduciary** (when it collects/owns the database) and a **Data Processor** (when it manages campaigns for clients).

- **The Shift:** You can no longer rely on "implied consent" or "public availability" as a blanket defense for B2B contact data.
- **The Risk:** Business contact information (e.g., `suresh.k@company.com`) is Personal Data under the Act. Processing it without a clear legal ground (Consent or Legitimate Use) invites penalties up to ₹250 Crore.

---

## 1. Critical Business Risks ("The Red Flags")

### A. The "Database-as-a-Service" Model
- **Risk:** Selling or renting access to a database of contacts to third parties is highly risky. Under the Act, you cannot transfer personal data to a client unless the Data Principal (the person in the database) has explicitly consented to that specific transfer.
- **Safeguard:** Transition from "selling data" to "brokering introductions."
  - **Action:** Do not share raw contact details with your client until the prospect explicitly opts in to be contacted by that specific client.

### B. OSINT & "Publicly Available" Data Trap
- **Risk:** The Act exempts "publicly available personal data" ONLY IF it was made public by the Data Principal themselves (e.g., a user tweeting their email) or under a legal obligation.
- **The Trap:** Scraping data from a third-party directory or a leaked database is NOT exempt. If a user posted their email on LinkedIn for "networking," scraping it for a sales list may violate the purpose-limitation principle.
- **Safeguard:** Tag every record in your database with its **Source of Origin**. If you cannot prove a record was self-disclosed by the user, delete it.

### C. "Intent-Based Intelligence" (Profiling)
- **Risk:** Analyzing user behavior to predict "intent" is automated processing and profiling. At high volumes this activity could get you notified as a **Significant Data Fiduciary (SDF)**.
- **Safeguard:** SDF status triggers mandatory Data Protection Impact Assessments (DPIA), an India-resident Data Protection Officer, and annual independent audits. Prepare for this higher compliance tier now.

---

## 2. Remaining DPDPA Obligations (Added Analysis)

These are the obligations the plan above does not yet cover. Each one is a standalone compliance requirement with its own penalty exposure.

### 2.1 Notice & Consent Mechanics (Sections 5–6)
- Notice must be given **at or before** collection, itemising: (a) the personal data collected, (b) the specific purpose, (c) how to exercise rights, and (d) how to complain to the Data Protection Board.
- Consent must be **free, specific, informed, unconditional and unambiguous**, given by **clear affirmative action** — no pre-ticked boxes, no consent bundled into Terms of Service.
- **Withdrawal must be as easy as giving consent** (one click, not an email to support). On withdrawal, processing must stop and downstream processors (e.g., your email vendor) must stop too.
- Notice available in **English and all 22 Eighth-Schedule languages**.

### 2.2 Data Principal Rights (Sections 11–14)
You must build workflows — not just a policy page — for:
- **Right to access:** a summary of what data you hold, what you did with it, and **every third party you shared it with** (this is lethal for a data-resale model: the access response itself exposes every client you sold the record to).
- **Right to correction and erasure:** correct inaccurate data; erase on request unless retention is legally required.
- **Right of grievance redressal:** respond within the prescribed timeline before the person can escalate to the Board.
- **Right to nominate:** a Data Principal can nominate someone to exercise rights after death/incapacity.
- **Duties of Data Principals** (Section 15) cut the other way too: users must not file false grievances — cite this in your grievance policy.

### 2.3 Personal Data Breach Obligations (Section 8(6) + Rule 7)
- On **any** breach (there is no materiality threshold in the Act), you must notify **each affected Data Principal** and the **Data Protection Board** — first intimation "without delay," detailed report to the Board within **72 hours**.
- Penalty for failing to prevent a breach: up to **₹250 Cr**; for failing to notify: up to **₹200 Cr**.
- **Action:** Write and rehearse a breach-response runbook (detect → contain → notify Board → notify principals → post-mortem). Keep a breach register even for near-misses.

### 2.4 Security Safeguards (Section 8(5) + Rule 6)
Minimum "reasonable security safeguards" the Rules expect:
- Encryption / obfuscation or tokenisation of personal data at rest and in transit.
- Access control on systems holding personal data (least privilege, no shared logins to the lead database).
- **Logs and monitoring** to detect unauthorised access — **retain logs and personal-data traffic records for at least 1 year**.
- Backups to ensure continued availability, and contractual security obligations flowed down to every processor.

### 2.5 Retention, Erasure & Purpose Exhaustion (Section 8(7) + Rule 8)
- Personal data must be erased once the purpose is served or consent is withdrawn — "we might sell this lead again someday" is **not** a purpose.
- The Rules prescribe erasure after prolonged user inactivity (draft: ~3 years for large platforms), with a **48-hour advance notice** to the user before erasure.
- **Action:** Define a retention schedule per data category (lead records, campaign logs, suppression lists, email logs) and automate deletion. A suppression list of hashed emails may be retained to honour opt-outs.

### 2.6 Cross-Border Transfers (Section 16)
- Transfers are allowed to any country **not on a government blacklist** — but the Rules can add conditions, and SDFs may face **localisation of specified categories**.
- If your clients or infrastructure (email APIs, CRMs, cloud) are outside India, map every cross-border flow and keep it in your Records of Processing.
- Note: DPDP applies **extra-territorially** to processing outside India if it targets people in India — offshore scraping entities don't escape the Act.

### 2.7 Children's Data (Section 9)
- Anyone **under 18** is a child. Processing needs **verifiable parental consent**; **tracking, behavioural monitoring and targeted advertising at children are prohibited outright**.
- Event/ABM relevance: student attendees at tech events and college hackathons are in scope. **Action:** exclude records where age/student status suggests under-18; never build "student intent" segments. Penalty: up to ₹200 Cr.

### 2.8 Processor Governance (Section 8(2))
- You may engage a processor (Resend, cloud hosts, enrichment APIs) **only under a valid contract**. The Fiduciary stays liable for the processor's failures.
- **Action:** Maintain a vendor register; execute DPAs with every sub-processor; verify their deletion on contract end.

### 2.9 Penalty Schedule (Section 33 + Schedule) — Know Your Exposure
| Violation | Max penalty |
|---|---|
| Failure of security safeguards | ₹250 Cr |
| Failure to notify a breach | ₹200 Cr |
| Children's data violations | ₹200 Cr |
| SDF obligation failures | ₹150 Cr |
| Any other violation | ₹50 Cr |

Penalties are **per instance** and the Board weighs repetitiveness and gains made — a data-resale business that ignores the Act compounds exposure with every sale.

### 2.10 Adjacent Laws (DPDP Is Not the Whole Picture)
- **TRAI TCCCPR / DND regime:** unsolicited commercial calls/SMS to Indian numbers have their own consent regime and penalties — relevant to tele-calling campaigns.
- **IT Act SPDI Rules 2011:** still apply until DPDP fully supersedes them.
- **GDPR / PECR / CAN-SPAM:** any EU/UK/US leads in the database pull in foreign regimes; GDPR fines (4% global turnover) stack on top of DPDP.

---

## 3. Strategic Action Plan: Compliance Checklist

### Phase 1: The "Legacy Data" Cleanup (Immediate)
- Legacy data (collected pre-Act) requires a **fresh notice** "as soon as reasonably practicable"; the right to withdraw applies to it.
- Run a **Re-permissioning Campaign**: "We are updating our privacy standards. Click here to confirm you still want to hear from us."
- **Hard truth:** delete the data of anyone who does not respond or opts out. Passive leads are now a liability, not an asset.

### Phase 2: Client Contract Overhaul
- **DPA:** contracts must state that when LeadStrategus acts as Processor, the Client (Fiduciary) owns the legal basis for the data it supplies.
- **Indemnity:** clauses protecting LeadStrategus if a client uses delivered data for spam that triggers a complaint.
- **Onward-transfer clause (added):** clients receiving leads become Fiduciaries in their own right — contractually oblige them to honour withdrawal/erasure signals you relay, and to notify you of breaches involving your data.

### Phase 3: The "Consent Manager" Architecture
- Integrate early with **registered Consent Managers** (interoperable consent platforms under the Act).
- Selling point: "We verified this lead's consent via [Consent Manager ID]" — the gold standard for B2B data verification.

### Phase 4 (added): Governance & Evidence
- Appoint a **Grievance Redressal Officer** (and a DPO if notified as SDF); publish contact details on the site.
- Maintain **Records of Processing** (what data, source tag, purpose, consent artefact, recipients, retention date) — this is your defence file when the Board asks.
- Consent artefacts must be **provable**: store timestamp, notice version, IP/interface. "They must have consented" is not evidence.
- Annual internal audit; DPIA for every new data product before launch.

---

## 4. This Product (Global Event Discovery Agent) — Specific Mapping

What this codebase actually touches, and what it needs:

| Area | Current state | DPDP action |
|---|---|---|
| Lead capture | Collects **work email** for the PDF report (`work_email.py`, `EmailReportModal.jsx`) | Add an unticked consent checkbox + inline notice (purpose, rights, GRO contact) at the point of capture; log the consent artefact |
| Storage | **Stateless by design** — PDF built in memory, nothing written to disk (`routes_email.py`) | Strong data-minimisation story; keep it that way and say so in the privacy notice |
| Email delivery | Sent via **Resend** (US processor) | Execute a DPA with Resend; disclose the cross-border transfer in the notice |
| Server logs | Loguru logs may capture emails/IPs | Redact emails in logs, or apply the 1-year retention + access-control rules to them |
| Privacy page | `frontend/dist/privacy/` exists | Update for DPDP: legal grounds, rights, GRO details, breach contact, languages plan |
| Event data | GPT-searched **event** data (companies, venues) | Mostly non-personal; but speaker/organiser names + emails are personal data — apply source-tagging if ever stored |
| Children | Public tool, no age gate | Low risk (work-email gate helps), but exclude student/under-18 targeting in campaigns built on this data |

---

## 5. Multi-Jurisdiction Client Engagements (UK Account Research, US / India / Europe ABM)

LeadStrategus runs delivery for clients across four regimes. **The law that applies follows the data subject (the prospect), not the client** — a UK client asking for research on German prospects puts you under EU GDPR, not just UK rules. DPDP compliance alone does not cover this book of business.

### 5.1 Jurisdiction Matrix

| Engagement | Governing law for prospect data | Legal basis for B2B outreach | Key exposure |
|---|---|---|---|
| **UK — account research / model building** | UK GDPR + Data Protection Act 2018 + PECR | Legitimate Interests possible for B2B research, **but requires a documented Legitimate Interests Assessment (LIA)** | ICO fines up to £17.5M / 4% global turnover; PECR for any resulting outreach |
| **US — ABM** | CAN-SPAM (email), TCPA (calls/SMS), state laws: CCPA/CPRA (California), Colorado, Virginia, Texas etc. | No consent needed for B2B email (opt-out regime), **but** CCPA gives Californians deletion/opt-out-of-sale rights — and "sale" includes sharing lead data for value | TCPA is the trap: $500–$1,500 **per call/text**, class-action driven; CCPA "sale" disclosures for lead resale |
| **India — ABM** | DPDP Act 2023 (this report) + TRAI TCCCPR/DND | Consent or Legitimate Use (narrow — no marketing carve-out) | Up to ₹250 Cr; DND penalties for tele-calling |
| **Europe (EU) — ABM** | EU GDPR + national ePrivacy laws | Legitimate Interests + LIA for research; **cold email consent rules vary by country** (Germany/Italy/Netherlands effectively require opt-in even for B2B) | 4% global turnover; Germany's UWG allows competitors to sue over cold outreach |

### 5.2 Account Research & "Model Building" (UK client)

- Building propensity/intent **models on personal data is profiling under UK/EU GDPR** — it needs a lawful basis of its own, separate from the outreach basis, and a **DPIA** if done systematically at scale.
- **Model building does not launder personal data.** If the training set was unlawfully scraped, the ICO's position is the derived model can be tainted too — regulators have ordered model deletion (ICO/FTC precedents on Clearview-style scraping).
- Individuals retain the **right to object to profiling** — you need a mechanism to exclude a person from models on request, not just from mailing lists.
- Account-level firmographics (company size, tech stack, funding) are **not** personal data — build models on those where possible; only contact-level fields (names, emails, job history, behaviour) trigger GDPR. This is the cheapest de-risking lever: **model at the account level, personalise only after a lawful basis exists for the individual.**

### 5.3 Cross-Border Architecture

- **UK/EU → India transfers:** India has **no UK or EU adequacy decision.** Every flow of UK/EU prospect or client data into LeadStrategus India systems needs **Standard Contractual Clauses (SCCs / UK IDTA)** plus a Transfer Risk Assessment. Without them the delivery model itself is unlawful, regardless of consent.
- **UK/EU representative:** processing UK/EU personal data without an establishment there triggers the **Article 27 requirement to appoint a local representative** for each regime.
- **Per-engagement roles:** define in each contract whether LeadStrategus is *processor* (client supplies the list, you execute) or *controller/fiduciary* (you source the data). Under GDPR, a processor that sources its own data **becomes a controller** with full obligations — most "we also enrich the list" engagements silently cross this line.
- **Segment the database by regime.** One pooled global lead database is the worst posture: an EU record mixed into an India campaign inherits GDPR, and vice versa. Tag every record with jurisdiction + source + legal basis, and gate campaign tools so a US ABM campaign physically cannot pull EU records.

### 5.4 Practical Rules per Campaign Type

- **US ABM:** email is opt-out (honour unsubscribes within 10 business days, no misleading headers, postal address in footer); never call/text without checking TCPA consent; screen California records for CCPA opt-out-of-sale.
- **Europe ABM:** country-by-country cold-email rules — maintain a matrix (opt-in countries vs. legitimate-interest countries) and route campaigns through it; sending one template to "Europe" is not compliant.
- **India ABM:** full DPDP program per Sections 1–3 of this report; use registered telemarketer headers for SMS/calls.
- **UK research:** LIA on file per project, DPIA for model building, honour objections, SCC/IDTA covering the data flow to India.

---

## Recommendation for the CEO

> "The era of 'bulk data' is ending; the era of 'verified data' is starting. We should pivot LeadStrategus to be a **Compliance-First Lead Partner**. We shouldn't just sell leads; we should sell **'Safe, Consented Leads.'** This justifies a premium price point and protects our clients from legal risk. Every obligation above — consent artefacts, source tags, breach readiness, consent-manager integration — is also a sales asset: it is the audit trail our clients will soon be forced to demand from every vendor."

---

*This report is an internal compliance analysis, not legal advice. Validate the final program with Indian data-protection counsel, especially SDF notification thresholds and the final DPDP Rules timelines.*
