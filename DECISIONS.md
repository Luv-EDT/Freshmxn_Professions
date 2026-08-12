# Design Decisions — locked

Everything agreed before Sector 2. Change these only deliberately.

---

## 1. Profession schema (final)

| field | meaning |
|---|---|
| `id` | stable slug. Join key for the psychometric pipeline. |
| `profession` | name a 15-year-old understands. No jargon. |
| `one_liner` | one plain sentence. |
| `job_roles` | concrete hiring titles. Specialisations live here, not as separate professions. |
| `role_spread` | `{ spread, deviating_roles[] }` — which job roles deviate from the profession's psychometric baseline. See §8.9 |
| `industrial_sectors` | many-to-many, from `industrial_sectors.json`. |
| `degree_dependency` | `none` / `certificate` / `undergrad` / `professional` |
| `mid_stream_entry` | `open` / `after_any_degree` / `restart_undergrad` |
| `class12_prerequisite` | **subject set**, e.g. `["physics","maths"]`, or `any` |
| `path_to_entry` | ordered steps — the answer to "how do I become one" |
| `entrance_exams` | `{ public_routes: [], private_entrances: [], note }` — see §4.36 |
| `entry_window` | time limits on routes, `null` if none. See §4.3 |
| `entry_competition` | `{ primary_gate, alternative_gates[] }` keyed into `entrance_gates.json`, `null` if entry is not competitively gated. See §4.35 |
| `licensing_body` | statutory body, `null` if unregulated |
| `years_to_qualify` | typical years from class 12 to first job |
| `economics` | `{ cost_of_entry_lakh, early_earnings_lpa, mid_career_lpa, mid_career_midpoint, payback_years, distribution, basis, verification }` — see §8.4 |
| `demand_signal` | `{ india_demand, pathway, note? }` — see §8.45 |
| `filter` | **derived** boolean. True = passes the compensation rule in `filter_rules.json`. See §8.5 |
| `after_undergrad` | `masters_required` / `masters_is_the_entry` / `masters_advantage` / `work_first` — see §8.7 |
| `self_employment` | `{ likelihood, ceiling_lpa, route, verification }` — see §8.7 |
| `ai_exposure` | `{ work_composition, legal_accountability, exposure_raw, band, reason }` — see §8.6 |
| `verification` | `{ tier, status, source, checked_on }` — see §7 |
| `nuances` | `[{ field, statement, source? }]` — settled subtleties. See §8.8 |
| `admin_review` | `{ required, priority, reason }` — unsettled decisions. See §9 |

**Dropped after discussion:** `alternate_route` (the whole tool is that) · `work_environment` (not now) ·
`entry_salary_band_inr` and `earning_note` (folded into `economics`) · `cost_barrier` (became
`economics.cost_of_entry_lakh`, now universal because the payback ratio needs a denominator) ·
`shipping` (replaced by the derived `filter` boolean).

`path_to_entry` is the source of truth. `class12_prerequisite` and `degree_dependency` are fast-filter
indexes derived from it.

## 8.4 `economics` — three numbers, not one

Entry pay alone is structurally biased toward long credentialed runways: it compares a 19-year-old welder
with zero debt against a 22-year-old engineer with 6 lakh of fees and calls the welder poorer. So:

- **`cost_of_entry_lakh`** — total typical cost of the standard route.
- **`early_earnings_lpa`** — years 1–3.
- **`mid_career_lpa`** — years 5–8 of **employment after qualifying**, **EMPLOYED only**.
- **`payback_years`** — derived, `cost / early midpoint`.

**`mid_career` excludes business ownership by design.** If a plumber's income depends on running a
contracting firm, the earning attribute is entrepreneurship — Sector 5 — not plumbing.

**Payback is a flag, not a filter.** It does not discriminate: every profession except Commercial Pilot
repays in under 2.5 years, and the *trades* have the best ratios in the dataset — Mason repays in 0.09
years at 3.0 LPA employed. **That is not a life ceiling, and this document used to say it was.**
See §8.7. Ranking by payback would put masons first. It is kept
because it correctly isolates capital risk, which for Commercial Pilot (4.07 years, 57 lakh self-funded)
is the whole story.

### `distribution` — what SHAPE the money is

Added after the 18-sector build, because six records had reached the point of saying *in their own
nuances* that their range was meaningless while `mid_career_midpoint` continued to drive the
`filter` boolean that decides whether a profession is shown at all. **A number the data calls
meaningless was gating visibility.**

| value | meaning |
|---|---|
| `range` | the ordinary case. A midpoint describes a typical person. **Default.** |
| `power_law` | a few earn enormously, most earn little, and there is almost no middle. **Exempt from the compensation filter** — deleting a profession on the strength of a midpoint that describes nobody is worse than showing it. |
| `bimodal` | two distinct populations, not a spread. The midpoint is correct arithmetic and describes almost nobody. |

Six `power_law`: Entrepreneur (S5) · Digital Content Creator (S9) · Actor (S10) · Professional
Athlete (S11) · Esports Professional (S11) · Coaching Faculty (S12).
Two `bimodal`: School Teacher (S12), KVS 8.3 lakh against private-school pay a fifth of it · Doctor
(S4), where **both pay and MBBS cost** are bimodal — **this closes the sector-wide question Sector 4
has carried open since it was built.**

Anything other than `range` forces `admin_review.required` — validator-enforced. A record saying
its own money cannot be averaged is describing an unsettled presentation decision, and §9 says
those belong to a human. **The enum records the shape; it does not decide how to display it.**

**All wage figures come from commercial salary aggregators, not government data.** India has no
authoritative free source for occupational earnings. This is the single largest known weakness.

## 2. The 18 professional sectors are fixed

Single parent. No profession in two sectors. **Overlaps push down to industrial tags, never up.**

- Teaching-anything → Sector 12, whatever the subject.
- Empirical research → Sector 3. Interpretation/heritage → Sector 17.
- **Method decides, not discipline.** Empirical and quantitative work goes to Sector 3 even when the subject is social — research psychology and demography sit there. Ethnography and cultural interpretation go to Sector 17. The discipline label is not the test.
- **But the QUESTION decides between 3 and 13.** Empirical work asking *did this specific programme work* is Sector 13 — the client is a funder, the output is accountability, and the finding does not generalise. Empirical work asking a question whose answer holds beyond the case is Sector 3. Monitoring & Evaluation Analyst is quantitative to its core and sits in 13 on exactly this line; without the sentence, §2 read literally would move it and lose the distinction between producing knowledge and proving a claim.
- **Intervene vs interpret** splits Sector 13 from Sector 17. A counsellor changes wellbeing (13). A historian explains it (17).

### 2.05 The 5 / 6 / 7 boundary

All three deal with organisations and money and rules, so the split is by **object of concern**:

| sector | object of concern | worked test |
|---|---|---|
| 5 Business, Management & Entrepreneurship | the organisation and its customers | Hospital Administrator — running an organisation is management whatever the organisation does |
| 6 Finance & Economics | money and value | Chartered Accountant, Actuary, Economist |
| 7 Law, Governance & Public Service | the state and the justice system | Company Secretary — delete company law and the role disappears |

The hard case was **Company Secretary**, which looks like finance and is not: its object of concern
is whether the organisation obeys the law. See §2.1.

### 2.06 Base-layer professions

**A pyramid needs its base listed, not only its apex.** Mason stands beside Civil Engineer; that is
now a pattern, not a one-off. Added on it so far: **Retail & Store Operations** and **Logistics &
Warehouse Operator** (Sector 5), **Accounts & Bookkeeping Executive** (Sector 6), **Paralegal &
Legal Support Executive** and **Firefighter** (Sector 7).

Two reasons, and the second matters more:

1. Industry employment figures count the base. Reading them as profession size is the §8.45 error.
2. **These are where students outside tier-1 cities actually are**, and they are often the only
   formal organised-sector entry available locally.

**Still owed** — bases with no home yet: apparel (Tailor, Garment Maker, Handloom Weaver) → 8 or
17 · agriculture (Farmer, Dairy Worker) → 15 · hospitality (Cook, Steward, Housekeeping) → 16 ·
beauty (Beautician, Hair Stylist) → 18 · healthcare (General Duty Assistant, Home Health Aide) → 4.

**Status after the 18-sector build and the review that followed:** apparel, agriculture,
hospitality, beauty **and healthcare** are all **closed**. The healthcare line closed last: Elder &
Home Care Attendant (the home) moved from Sector 18 into Sector 4, and General Duty Assistant (the
ward) was added beside it. **Urban & Regional Planner** was also added to Sector 2 — not a base
layer, but the same class of miss: §4 used B.Plan as its worked example of the
`class12_prerequisite` rule and `verified_facts.json#jee-main-paper2b-bplan` had been fetched and
verified, yet **no profession in any of the 18 sectors consumed it.** A fact existed for a
profession that did not.

*(superseded detail, kept for the record)* — Tailor, Handloom Weaver and Handicraft Artisan in 8; Farmer in 15; Cook, Steward and Housekeeping in 16; Beautician and Hair Stylist in 18. The healthcare line is **half open**: Sector 18 built *Elder & Home Care Attendant*, covering care in the home, which is where the substitution test is weakest — swap the home for a ward and the work survives, which argues the whole record belongs in Sector 4. **General Duty Assistant, the hospital half, has no record anywhere.** Both need one decision together, and Sector 4 is built.
**Private security** (~9 million people) has no home at all: it fails the Sector 7 test, since
private security does not exist because the state exists.

**DECIDED, 2026-08-12 — private security is OMITTED, and this is a decision rather than a gap.**
The independent review argued for reopening it: Firefighter already sits in Sector 7 and a factory
fire crew does not exist because the state exists either, so §2.1's test was arguably written for
the *legal* professions rather than for the protective-services family Sector 7 actually contains.
That argument was heard and overruled on a different ground — **that AI surveillance will reduce
guard headcount.**

Recorded honestly, including its weakness: **no sourced headcount trend supports the decline
either way.** The argument is strongest for the CCTV and monitoring roles, which analytics does
substitute for. It is weakest for the guard at the gate, whose function is presence, intervention
and giving the client someone to hold liable — surveillance *detects*, it does not stop anyone.
PSARA 2005 formalisation has also been pushing this workforce toward licensed agencies rather than
away.

**If the decline is ever sourced, the rule says list it as `declining`, not omit it** — §8.45's
only ground for omission is work that has actually died. Until then the taxonomy is silent on
roughly nine million people by choice, and this paragraph is why.

### 2.1 Sector 7 boundary

Three families: **Law & Justice** (lawyer, judge, prosecutor) + **Civil & Administrative Services** (IAS, IPS, IRS) + **Policy & Diplomacy**.

> Only careers whose work **exists because the state or justice system exists.** A profession that merely works *for* government stays in its home sector with a Government industrial tag.

**The test cuts both ways — it is not about who pays you.** A corporate lawyer is paid by a company
and still belongs here, because without law there is no job. A doctor in a government hospital is
paid by the state and does not, because without the state there are still sick people.

**Company Secretary belongs here, not in Finance.** Decided while scoping Sector 5; recorded now so
Sector 7 does not have to re-derive it. A CS is not a secretary, not a founder's-office generalist
and not a ministry Secretary — the shared word is a historical accident. Under the Companies Act
2013 a CS is a statutory **Key Managerial Personnel** alongside the CEO and CFO, mandatory for
listed companies and companies above a paid-up-capital threshold, personally liable for the
company's regulatory filings. Apply the test: **delete company law and the role disappears entirely.**
Its object of concern is whether the organisation obeys the law, which is governance, not money.

It is a *separate* profession from Corporate Lawyer, not a merge: different statutory qualification
(ICSI, three stages plus training, versus LLB and Bar Council enrolment) and different daily work
(board process, statutory registers, secretarial audit, ROC filings, versus contracts, transactions
and advisory).

### 2.2 Cross-cutting rule — big employers are TAGS, not sectors

Defence and Armed Forces, Police, ISRO, Railways, Government span many professions. They are **industrial sector tags.**

The **uniformed or institutional identity** goes to Sector 7. **Specialist roles keep their home sector** and carry the tag.

| case | sector | tag |
|---|---|---|
| Army officer | 7 | `EXT-DEFENCE` |
| Army doctor | 4 | `EXT-DEFENCE` |
| Air Force pilot | 2 | `EXT-DEFENCE` + `AASSC` |
| ISRO propulsion engineer | 2 | `AASSC` + `EXT-RND` |
| ISRO research scientist | 3 | `EXT-RND` |
| Railway civil engineer | 2 | `EXT-GOVT` + `CSDCI` |
| Police officer (IPS) | 7 | `EXT-DEFENCE` |
| Police forensic scientist | 3 | `EXT-DEFENCE` |
| Government school teacher | 12 | `EXT-GOVT` + `EXT-EDU` |

`EXT-GOVT` was split into `EXT-GOVT` (civil administration, Railways, PSUs) and `EXT-DEFENCE` (armed forces, police, paramilitary) to make this rule expressible.

### 2.25 No seniority tiers

**A profession is an entry identity, not a career ladder.**

Never list a profession that is simply the senior version of one already present — no Senior Engineer, Head of Design, Chief Architect. Two reasons: the audience is choosing what to *become*, not what to be promoted to; and senior roles across almost every sector converge on management, which is not a distinct professional identity.

This applies to `job_roles` too — they show the *range* of a profession, not its ladder.

`after_undergrad` already carries the "what comes next" information, which is all this audience needs.

### 2.3 Audience

Four journeys, not one age group: **9th–10th** (stream not yet chosen) · **11th–12th** (stream locked) · **college** · **early professionals**.

"Understandable to a 15-year-old" is a rule about **naming**, not about who the tool serves.

Every sector file carries `routed_elsewhere` — professions a reviewer expects to find there and won't, with destination and reason. It is an audit trail, not a task list. A validator will later enforce that every routed profession actually lands at its destination.

---

## 3. `degree_dependency` — the strict test

**What stops you getting the first job** — *not* what's the best preparation. Without this guardrail everything drifts to `undergrad`.

| tier | test |
|---|---|
| `professional` | Practising without it is **illegal**, or you cannot register with the statutory body. |
| `undergrad` | Not legally required, but **either** hiring pipelines genuinely filter on it, **or** the foundations cannot realistically be self-assembled. |
| `certificate` | Structured training needed, but a short credential delivers it. ITI, diploma, NSQF, vendor cert. |
| `none` | Hired on demonstrated output. Portfolio, audition, trial. |

### ⚠️ Never use it as an eligibility filter

It describes the **destination, not the door**. `professional` contains both the most and least reachable careers in the dataset — Law and MBBS are both `professional`, but a commerce undergrad reaches Law in 3 years and cannot realistically reach MBBS at all. Use it for cost and display only.

---

## 4. Reachability

### `mid_stream_entry`
- `open` — start now, alongside or instead of current studies.
- `after_any_degree` — the gate opens *because* you hold a degree, any degree. LLB (3-yr), MBA, MCA, CA direct entry, B.Ed, M.A. **These look hard but are the most reachable options for a college student.**
- `restart_undergrad` — must re-enter UG year 1 via entrance exam. Costly, not forbidden.

**Always describes the *entry* credential, never the advanced one.** M.Tech, MD/MS, MDS, LLM are advancement *within* a profession → they go in `job_roles`. This is why there is no fourth value.

### `class12_prerequisite`
A **subject set**, not a stream. Streams produce false exclusions in both directions:
- PCMB students satisfy both maths and biology gates — a 3-bucket model can't say that.
- B.Tech needs `{physics, maths}` — Chemistry is *not* compulsory. Physics + Maths + Computer Science qualifies.
- B.Arch needs `{physics, chemistry, maths}`.
- B.Plan needs `{maths}` only.

Set a subject only when an entrance exam or degree admission literally requires it. If a genuine non-degree route exists, the value is `any`.

**This field carries the class-10 stream decision — the most irreversible choice in Indian schooling.**

### 4.3 `entry_window` — time limits belong to the ROUTE, not the profession

Some entrance exams expire. **JEE Main admits roughly a 3-year window from class 12.**

**A profession is blocked only when every route is blocked.**

```json
"entry_window": {
  "max_years_since_class12": 3,
  "max_age": null,
  "is_hard_block": false,
  "constrained_route": "JEE Main — admits roughly three years of class 12 cohorts",
  "bypass": "3-year diploma then lateral entry into B.Tech year 2, or B.Sc lateral entry. AICTE sets no maximum age for lateral entry."
}
```

**Exactly these five keys**, pinned in `export_csv.py` as `ENTRY_WINDOW_KEYS`.

**Engine rule:**
- `null` → no time constraint
- `is_hard_block: false` → narrow the route, **show the `bypass`**, never exclude
- `is_hard_block: true` → exclude, and say why

The validator rejects `is_hard_block: false` with no `bypass`, and `true` with a `bypass`. That
contradiction is exactly the error made when this was first raised: an expiring *exam* was read as
a closing *profession*.

**An earlier version of this section predicted "real hard blocks are expected in Sector 7 — NDA and
UPSC carry genuine statutory age caps with no bypass." Sector 7 was built and that is wrong.**
Both are `is_hard_block: false`, because both have a real bypass: state Public Service Commissions
run to 38–40 where UPSC stops at 32, and CDS and AFCAT reopen officer entry after a degree when
NDA has closed at about 19.5. **There is still no hard block anywhere in the taxonomy.**

---

### 4.36 `entrance_exams` — two arrays, and what each is for

```json
"entrance_exams": {
  "public_routes":     ["NEET UG", "State nursing entrance exams"],
  "private_entrances": ["BITSAT", "COMEDK"],
  "note": "…"
}
```

- **`public_routes`** — every government-run route, **national AND state**. State PSCs, state
  police boards, state nursing and allied-health entrances belong here.
- **`private_entrances`** — private college entrances only. Cap at ~5 genuinely reputed;
  state-scoped consortia like COMEDK are fine, since a Karnataka student really does sit COMEDK.
- **Neither holds licensing or certification requirements.** NISM registration, CFP and the
  Insurance Institute examinations are things you must hold to practise, not doors you compete
  through — they belong in `path_to_entry` and `licensing_body`.

**These were previously named `national` and `private_reputed`, and the names lied.** `national`
held seven state-level exams across fifteen professions; `private_reputed` held a SEBI registration,
two professional certifications, and CUET (LLB) — a *public* test. Renamed and cleaned, correction
#11 in §10.

---

### 4.35 `entry_competition` — the odds, and what you keep if you lose

The largest risk the schema could not express: a candidate can spend three to six full-time years
on a government examination and hold no credential at the end. `entry_window` says whether a door
is open; this says **how many people are trying to get through it, and what happens to those who
do not.**

Numbers live once in **`data/entrance_gates.json`**, not on the profession. Gates are shared —
five professions sit behind NEET, six behind CAT — so per-profession figures would be copies that
drift apart. A profession only names its gate:

```json
"entry_competition": { "primary_gate": "upsc-cse", "alternative_gates": ["bitsat"] }
```

**Two mechanisms, because they fail differently:**

| mechanism | the filter | example |
|---|---|---|
| `seat_limited` | a fixed number of places; competition is applicants per seat | UPSC 1,096:1 · CAT 41:1 · CLAT 25:1 · NEET 18.7:1 |
| `attrition_limited` | no quota at all; the filter is the pass mark | CA Foundation, 20.1% pass |

#### Preparation is never worth nothing

`if_unsuccessful` separates two things that get confused:

```json
"if_unsuccessful": {
  "credential_gained": null,
  "transfers_to": ["State PSC", "SSC CGL", "IBPS PO", "teaching", "policy research"],
  "non_credential_gain": "Working knowledge of Indian polity, economy and history…"
}
```

The **credential** is usually the hard loss. The **knowledge and the adjacent routes are not** — a
failed UPSC candidate carries their preparation directly into every other government examination,
into teaching, journalism and policy. `audit.py` **rejects a gate whose `transfers_to` is empty**:
claiming preparation is worthless misleads a family toward despair as surely as overselling it
misleads them the other way.

**Consequence for §5:** failed full-time preparation is **not** waste at weight 1.0. It behaves
like undergrad year 3+ — partly sunk, partly carried forward.

#### The money-for-odds trade

A `private_reputed` gate is usually winnable at odds a public gate is not, for a much larger fee.
**Reporting the odds without the price tells a rich student the truth and a poor one a lie**, so
`typical_total_cost_lakh` is mandatory on every private gate and the validator enforces it. BITSAT
is the worked case: ~4,000 seats, and roughly ₹23.5 lakh for the four-year B.Tech.

> **Medicine is the exception, and it is already verified.** NEET governs government, private
> **and deemed** colleges alike (`verified_facts.json#neet-ug-eligibility`). It is the one gate in
> the registry where money cannot convert a competition problem into a cost problem.

---

## 5. Scoring — switching cost

```
score = psychometric_fit × exp(−effective_waste / τ)
```

The exponential is a standard time-discounting curve borrowed from economics. **It is not from career-guidance research.** Treat τ and the weights below as a starting calibration to tune against real outcomes.

### What counts as waste

**A completed qualification is never waste. Only abandoned study is.**

| giving up | weight | why |
|---|---|---|
| Class 11–12, wrong stream | 1.0 | must be redone |
| Undergrad year 1–2 | 1.0 | credits don't transfer, cheap to leave early |
| Undergrad year 3+ | 0.5 | close to done, skills and maturity carry |
| Employment years | 0.3, **capped at 3.0** | income, network, work skills transfer |
| Anything completed | 0.0 | it's an asset |

**Override:** if the target is `after_any_degree` or `open`, waste = **0**. Don't abandon — finish, then switch. Correct real-world advice, encoded.

The employment cap is what stops a 20-year veteran being penalised into oblivion.

### τ — how much a year costs you now

| stage | τ |
|---|---|
| pre-10 | ∞ (multiplier = 1.0) |
| class 11–12 | 20 |
| undergrad | 8 |
| working 1–3 yrs | 4 |
| working 4+ yrs | 2.5 |

School students have waste = 0 for everything, so every multiplier is 1.0. **The exponential does nothing for the primary audience — it only activates for switchers.** That is the intent.

### Why sunk cost only, not years-ahead

Scoring years-ahead wipes out whole sectors at once — every Healthcare profession is a long path, so it would vanish for every college student simultaneously. That's a calibration bug, not a finding.

**The gap, and the patch:** sunk cost can't tell a 3-year path from a 9-year path. So **display `years_to_qualify` beside every result.** Ranking uses waste; the runway is always visible.

```
Lawyer   fit 0.71  ·  3 years to qualify
Doctor   fit 0.55  ·  9 years to qualify
```

### Guard against conservatism

Fit × cost makes the algorithm structurally timid — it will never tell anyone to make the hard change even when that's the true answer. So **always show two lists**:

1. **Reachable from here** — cost-weighted.
2. **Worth the switch** — top 3 by **raw fit only**, cost shown but not applied.

---

## 6. The inversion — the real deliverable for school students

A 15-year-old doesn't need 300 ranked professions. They need to know **what each stream costs them.** Once `class12_prerequisite` exists, invert the query:

> "Here are your top 50 matches. **Commerce** keeps 38 open. **PCM** keeps 34. **PCB** keeps 21."

This is the most useful output for the pre-10 audience, it addresses the most irreversible decision in Indian schooling, and it falls out of the field for free.

---

## 7. Verification policy

**Nothing ships as fact unless fetched.** Every record carries `verification.status` = `verified` or `judgment`. Never anything between.

| tier | what | source |
|---|---|---|
| **A** | Regulated — a statutory body controls entry | NMC, DCI, INC, PCI, VCI, NCISM, BCI, COA, ICAI/ICSI/ICMAI, RCI, NCTE, IEI |
| **B** | Entrance-gated, not licensed | Official exam eligibility pages — JEE, NEET, NATA, CLAT, CUET, NID DAT, NIFT, ICAR AIEEA |
| **C** | Open market — **no authority exists** | NCO 2015, NSDC QP-NOS confirm the occupation is real. `degree_dependency` here is a **judgment call and labelled as one.** |

Roughly two-thirds of professions are Tier C. Salary bands are always `judgment`.

Tier A/B facts get a `checked_on` date, because **rules change** — the B.Arch prerequisite changed with the CoA 2020 regulations, and quoting the old rule was a real error caught in review.

Verified facts shared across sectors live in `data/verified_facts.json` so they're fetched once and audited in one place.

**Cost:** ~5–8 fetches per sector, not 300.

### 7.1 An OFFICE is not a LICENCE — the test before naming a `licensing_body`

A `licensing_body` is only real if there is **unlicensed practice for it to police**. Ask one
question:

> **Could someone do this work without permission, and would that be unlawful?**

If yes, a licence exists and a body can strike you off — Doctor, Architect, Advocate, Chartered
Accountant. If the work is **impossible** without an appointment, it is an **office**, not a
licence: there is no unlicensed judge, no unlicensed IAS officer, no unlicensed colonel. An office
takes `licensing_body: null` and **Tier B** — the exam that appoints you is the gate.

Two traps this rule closes:

- **A prerequisite is not a licence.** Bar enrolment is required to *apply* for judicial services,
  so it belongs in `path_to_entry`, not `licensing_body`. Needing a credential to enter the
  competition does not mean that credential's body regulates the job you win.
- **The body must be the one that regulates *this* work.** A plausible, real, correctly-spelled
  body is still wrong if it does not control this occupation. The BCI cannot discipline a judge; a
  judge who takes office **surrenders** Bar enrolment to the non-practising roll.

**No tool can catch this.** Every automated check passed on Judicial Services Officer — the field
was populated, the body existed, the source resolved, the record was `verified`. Only a human
asking "is that body actually the one that licenses *this*?" found it (§10, correction #22).

Consequence for `degree_dependency`: an office is `undergrad`, not `professional`. `professional`
means *a licence gates the work*, and `audit.py`'s coupling
`degree_dependency == "professional"` ⇒ requires `licensing_body` is correct **because** of this
rule, not in spite of it.

---

## 8.45 `demand_signal` — demand and pathway are different questions

Conflating them is an error made and corrected here. Biomedical Engineering was nearly written off because
Indian degrees underdeliver — but India **imports** most medical devices, which is evidence of demand, not
its absence. A weak pathway is a supply problem, not a demand problem.

- **`india_demand`** — `high` / `moderate` / `low` / `declining`. Does society need this work?
- **`pathway`** — `india` / `any` / `abroad`. Where can you realistically train for it?

### The four values, and the one that is not there

| value | meaning |
|---|---|
| `high` | hiring at volume today |
| `moderate` | steady, unremarkable hiring |
| `low` | thin market, few posts — **but stable**. Physicist and Mathematician live here: few chairs, not a shrinking field. |
| `declining` | total employment is **structurally shrinking** because technology is absorbing the work itself |

**`low` and `declining` are different claims.** `low` is about size, `declining` is about direction.
Biomedical Engineer is `low` because India imports its devices — a market shape that has never been
large, not a trend. CAD Draughtsman is `declining` because parametric CAD and generative tools are
eating the drawing work itself.

**`declining` is not a filter and never removes anything.** A declining profession still pays today
and is still listed; the tag lets the application say so. Because it is a claim that someone's field
is shrinking, `export_csv.py` **rejects `declining` unless a `nuance` on `demand_signal` explains
why** — the assertion may never be made bare.

### Industry size is NOT profession size

An industry's employment figure counts everyone in it. A profession counts only the people doing
that profession. **Most large Indian industries are pyramids with a very wide operator base and a
very narrow professional apex**, so the two numbers can differ by three orders of magnitude.

**Textiles is the worked example.** The industry is India's second-largest employer, and the
demand tag for Textile Engineer is `low`. Both are true:

| layer | who | roughly |
|---|---|---|
| base | handloom and powerloom weavers, garment machine operators, spinning and dyeing hands | tens of millions |
| middle | supervisors, mechanics, quality checkers | large |
| apex | **B.Tech textile engineers** | ~50 degree programmes nationally |

Three things keep the apex narrow. The industry is **labour-intensive and decentralised** — a
twenty-worker powerloom unit has no engineer, the owner runs it. The engineering that does happen
is largely done by **generalists**: mills hire mechanical engineers for maintenance, chemical
engineers for dyeing, electrical engineers for plant power, because those graduates are abundant.
And the **machinery is imported**, so India does little textile-machine design — the same import
logic that makes Biomedical Engineer `low`.

**Before tagging demand from an industry statistic, ask which layer the profession sits in.**
This will recur, and harder:

| sector | huge employment | but the profession is |
|---|---|---|
| 15 Agriculture | ~250 million in agriculture | Agricultural Engineer, Agronomist — tiny by comparison |
| 2 Engineering | construction is a top-three employer | already handled: Mason and Civil Engineer are **separate professions**, base and apex |

**Construction shows the fix.** The base is not missing there — Mason, Plumber, Carpenter, Welder
and Heavy Equipment Operator are professions in their own right beside Civil Engineer. Textiles has
no such base in the taxonomy yet: `AMHSSC` is carried by only two records, both of them apex ones.

> **OPEN COVERAGE GAP.** Tailor and Garment Maker, Handloom Weaver and similar apparel trades are
> not yet represented anywhere. They are base-layer professions for an industry of tens of millions
> and must be placed when **Sector 8 Design & Creative Arts** and **Sector 17 Humanities, Culture &
> Belief** are built — craft-production versus heritage-craft is the boundary to settle then.

### The only reason to drop a profession

> **Drop only when the demand has structurally collapsed through technological obsolescence** —
> typewriter mechanic, stone tool maker. Nothing else qualifies.

Not low pay (the compensation filter is derived and reversible, and the record survives). Not high
AI exposure — **`ai_exposure` speaks for itself and the application frames the warning; the database
owes nothing further.** Not weak graduate outcomes — Dentist oversupply and the Aircraft Maintenance
Engineer licence drop-off are supply-side facts, recorded as nuances, and the professions stand.

There is deliberately **no `obsolete` value**: work that has actually died never gets entered, so
nothing in the data should ever carry the tag. A profession that reaches obsolescence is deleted and
recorded in the sector `changelog`, not marked.

**`pathway` deliberately does not rate Indian institutions as strong or weak.** It states where the
training exists, which is factual and actionable. `abroad` marks professions where the real version of
the work needs training outside India — those get an abroad-programmes dataset later.

Keeping the two orthogonal is the point. Collapsing them into one score reintroduces the original error.

## 8.5 How every field is used — filtering, sorting, scoring

**Governing principle: nothing is removed unless it is genuinely impossible. Everything else is a bounded nudge or a user control.**

| field | role |
|---|---|
| `class12_prerequisite` (unsatisfiable, no bypass) | **HARD FILTER** — removes |
| `entry_window.is_hard_block` | **HARD FILTER** — removes |
| compensation filter | **DERIVED at query time** from `economics` + `filter_rules.json`. Never stored. |
| wasted years | **SCORE** — the exponential, §5 |
| `ai_exposure` | **SCORE** — capped 15%, horizon-scaled, §8.6 |
| `years_to_qualify` | display + user filter ("only ≤2 years") |
| `entry_salary_band_inr` | display + user sort |
| `degree_dependency` | display + user filter ("no-degree options only") |
| `after_undergrad` | display, surfaced for the college journey |
| `self_employment` | display + user filter |
| `entry_window.bypass` | display — tells the student the other door |

Full score:

```
score = fit
      × exp(−wasted_years / τ)              ← switching cost, §5
      × (1 − ai_penalty × horizon_weight)   ← §8.6
```

## 8.6 AI exposure — the knowledge / skill / clarity model

Do not predict. **Describe what the work is made of**, and let exposure follow from which layers have already been commoditised.

**Four things protect a profession from AI. Only two layers are exposed.**

```
        ┌─ PSYCHOMETRICS ─────────────────────────────┐
        │  multiple intelligences, personality,        │  ← sits above everything
        │  cognitive & meta abilities                  │     NOT stored here — separate pipeline
        └──────────────────────────────────────────────┘
                            ▲ matched against ▼
   CLARITY              ─── protective ── clarity of OBJECTIVE and PROBLEM: what, how, for whom, and why
   SKILL   physical     ─── protective ── hands in the real world
           digital      ─── EXPOSED ───── output a model can produce
   KNOWLEDGE
           foundational ─── protective ── mental models you reason with, and judge AI output with
           retrievable  ─── EXPOSED ───── lookup facts, commoditised by the internet
```

```
exposure  = knowledge_retrievable + skill_digital
protected = knowledge_foundational + skill_physical + clarity
```

`work_composition` carries all five and must sum to 100.

| raw | band | penalty |
|---|---|---|
| ≥ 65 | high | 15% |
| 40–64 | medium | 7% |
| < 40 | low | 0% |

**What `clarity` means, precisely.** Clarity of **objective** and clarity of **problem** — knowing *what* is actually being solved, *how* it should be approached, *for whom*, and *why it matters*. It includes deciding what to ignore and owning the consequences of the call.

The "for whom" is doing real work in this definition. A model can produce an answer; it cannot know whose problem it is, what that person actually needs versus asked for, or what a good outcome looks like *to them*. That is why an IT Business Analyst (55% clarity) is the safest desk job in Sector 1 — the entire job is establishing what a room of people who disagree actually want.

**Why knowledge splits.** Not all knowledge was commoditised. Looking things up was — the mental models that let you reason at all, judge whether an AI answer is right, and direct the tool are not. Without a base layer you cannot even use AI competently. So foundational knowledge is a **moat**, and only retrievable knowledge is exposed.

**Why skill splits.** An electrician and a Photoshop artist are both ~60% skill; AI takes one and not the other. Where the output is physical, trained skill is a **moat, not a liability.** This single condition is what makes the model work across all 18 sectors instead of only the desk-bound ones — without it, every trade in Sector 2 would be wrongly condemned.

**`legal_accountability`** stays as a separate dampener and **moves the band down one step.** A licensed human must still sign even when the underlying tasks automate — radiology work changes, radiologists persist. It is structural rather than compositional, so the composition cannot express it.

The validator recomputes `exposure_raw` and `band` from the composition and rejects any mismatch — the label can never drift from the stated evidence.

**Where psychometrics fits.** It sits above this whole stack and is *not* stored in this schema. `clarity` is the profession-side quantity that the psychometric layer will be matched against.

**Why this replaced the earlier checklist:** the checklist listed symptoms. This explains the mechanism.

Scaled by how far the student is from entry — the only honest confidence signal:

| journey | weight | max hit |
|---|---|---|
| 9th–10th | 1.0 | 15% |
| 11th–12th | 0.8 | 12% |
| college | 0.5 | 7.5% |
| early professional | 0.25 | 4% |

**Capped at 15%** — enough to reorder near-ties and push future-proof careers up for a 9th-grader, never enough to bury a strong match. The cap *is* the honesty: this matters, but not enough to dominate.

**Two rules:**
- **Frame it as "the bottom rung shrinks," not "the career dies."** AI hits entry-level work hardest, which is exactly where a graduate walks in.
- **Name the roles.** Manual QA and SDET face opposite futures inside one profession. `reason` must say which.

Any profession scoring `high` is auto-flagged for admin review.

## 8.7 `after_undergrad` and `self_employment`

For the college journey, "master's or start working?" is *the* question. Generic advice fails because the answer differs by profession.

| `after_undergrad` | meaning |
|---|---|
| `masters_required` | cannot practise without it — Clinical Psychologist, Professor | undergrad is specific
| `masters_is_the_entry` | the PG *is* the door — consulting via MBA | undergrade is any
| `masters_advantage` | meaningfully helps, not required — core engineering |
| `work_first` | industry values experience; do it later if ever — software, design |

`self_employment`: `common` / `possible_later` / `rare`. In India this is a major income path the tool would otherwise ignore — CA practice, independent lawyer, freelance designer, private tutor — and it is what makes "job, freelance or startup" answerable.

## 8.7b `self_employment` — and why there is no status field

`mid_career_lpa` is **employed-only** (§8.4). For most professions that is the whole picture. For
the trades it deletes the half where they win, and this document then called the result a trap.

```json
"self_employment": {
  "likelihood": "common",           // common | possible_later | rare
  "ceiling_lpa": "6-18",            // null unless SOURCED
  "route": "ITI, then a state electrical contractor licence, then your own client base.",
  "verification": { "status": "verified", "sources": ["…"], "checked_on": "…" }
}
```

- `likelihood: "rare"` ⇒ `ceiling_lpa`, `route` and `verification` all null.
- Otherwise **`route` is required** — the honest answer to "how do I actually get there?"
- `ceiling_lpa` is **money** and obeys every money rule. Only 3 of 45 could be sourced:
  Electrician, Automobile Mechanic, AC & Refrigeration Technician. The rest are `null` with an
  `admin_review`, because a number we cannot source is owed, not absent.

**The counter-fact that keeps this honest.** Self-employment is not secretly better on average:
Indian self-employed workers average about ₹13,200 a month against ₹21,000 for salaried. The
ceiling is a **ceiling** — reachable, not typical. Never present it as the expected outcome.

### No field ranks social status

A `societal_tier` field was requested and **rejected**: it would write a caste-and-class hierarchy
into a database aimed at 15-year-olds, it is perception rather than fact, and as a sort key it
buries the most AI-proof careers we have.

Two factual substitutes were then designed and **also dropped**:

- **`work_conditions`** — dropped as unnecessary once the ceiling was fixed.
- **`employment_formality`** (`organised`/`mixed`/`informal`) — dropped because it **fails at its
  own job**. The organised/unorganised split describes the *enterprise*, so a funded startup
  founder and a daily-wage mason both classify `informal`. A field meant to carry "respectable"
  that groups those two carries nothing.

> **The conclusion:** there is no honest single field that encodes respectability. Any factual
> field groups the founder with the mason, because factually they share a great deal — no employer,
> no PF, variable income. What separates them is *status*, and status is not ours to record.

**The aspiration need is met by a query, not a column.** `data/filter_rules.json` carries a
`preference_filters.formal_workplace_track` preset — `credentialed OR NOT manual` — which keeps 74
of 83 and removes exactly the nine manual building trades, while keeping EMT, Laboratory
Technician, Precision Manufacturing Technician and IT Support. It is **derived at query time,
stored nowhere, and never a default**, and the application must state its cost: it removes the nine
most AI-proof careers in the dataset (mean exposure 9.1 against 28.7 for what it keeps).

## 8.8 `nuances` — settled subtleties a tag can't carry

Some facts are true, verified, and make a tag value misleading on its own. Architect carries
`licensing_body: "Council of Architecture"` — but the Supreme Court has held that registration
protects the **title**, not the **activity**. The tag isn't wrong; it's incomplete.

```json
"nuances": [
  { "field": "licensing_body",
    "statement": "CoA registration protects the TITLE 'Architect', NOT the activity...",
    "source": "data/verified_facts.json#coa-architect-title-protection" }
]
```

**The rule that stops this becoming a dumping ground:**

> **`nuances` are SETTLED. `admin_review` is UNSETTLED.**

A nuance is something true we already know. An admin_review is a decision a human still owes.
The audit rejects any nuance containing *"not yet verified"*, *"needs verification"*,
*"unverified"* or *"confirm before"* — that text belongs in `admin_review`.

Every nuance must name a `field` that actually exists on the record. Also validator-enforced.
Without that, "nuance" degrades into free-text commentary attached to nothing.

## 8.9 `role_spread` — when one profession contains two different people

Job roles inside a profession do not always want the same person. A Penetration Tester and a
GRC Analyst are both Cybersecurity Specialists and are close to opposites.

`role_spread` records which roles deviate, **in the 19 factors the psychometric pipeline
already scores**, so it feeds the pipeline rather than sitting as prose.

```json
"role_spread": {
  "spread": "wide",
  "deviating_roles": [{
    "roles": ["Production Engineer", "Maintenance Engineer", "Quality Engineer"],
    "higher": ["conscientiousness", "attention_span", "bodily"],
    "lower":  ["openness", "spatial"],
    "why": "Plant-floor work rewards routine discipline and physical presence. The design side of this profession rewards abstraction and tolerance for ambiguity."
  }]
}
```

**Rules, all validator-enforced:**
- `higher` / `lower` are **relative to the profession's own baseline** — never absolute scores.
  All real scoring stays in the separate psychometric pipeline. This field only says *where
  inside a profession the profile shifts.*
- Factor names must exist in `data/psychometric_factors.json` (the 19 factors).
- Every role named must exist in that profession's `job_roles`.
- `narrow` ⇒ `deviating_roles` empty. A factor cannot be both higher and lower. Every group
  needs a `why`.

**22 of 65 professions are `wide`.** Most are narrow — the flag is meaningful precisely because
it is uncommon.

## 8.95 What makes something a profession — the demand-side test

> A **self-sufficient, easy-to-understand field a student can pursue**, identified by
> **affinity for the sector's object of concern + a separate skill set**, meeting a **need that
> exists in society**, and containing multiple job roles.

**Three parts, all required.** An earlier supply-side test — "distinct if reaching them requires a
different educational decision" — was **wrong**: it described how you get in, not what the work is.
An earlier two-part version said "interest alignment" without saying *interest in what*, which let
an industry masquerade as an interest and put Medical Coder in Healthcare for a whole lock cycle.

### The demand side, stated

**The need comes first, and the qualification second.** A profession earns its place because
society needs the work done — not because a degree for it exists in India, and not because Indian
institutions currently teach it well. If India imports every semiconductor it uses, the demand for
chip designers is real *here* even while the supply of Indian training is thin; the answer is the
`demand_signal.pathway` field (`india` / `abroad` / `any`), not deletion.

The inverse also holds: **a degree existing is not evidence of demand.** A course with seats and no
need behind it is a supply-side artefact. This is why `demand_signal` is a separate field and why
weak-outcome professions like Biomedical Engineer carry an `admin_review` instead of a clean listing.

### Object of concern ≠ industry domain

The first half of the test is **not** "which industry employs you." It is **what you care about** —
a real thing in the world: health, learning, justice, land, story, the built environment, the body.
Someone can care about *health* without any clinical skill at all.

**The 18 professional sectors ARE the objects of concern.** Sector 4 is not "the healthcare
industry", it is **health**. Sector 12 is not the education industry, it is **learning**. That is
why the taxonomy needs no third axis: the sector already carries the affinity, and
`industrial_sectors` carries the employer.

**The substitution test** decides which one you are looking at:

> Swap the industry out. If the work survives essentially unchanged, the industry was only a tag.
> If the work becomes incoherent, the object of concern is real and it sets the sector.

| profession | swap the industry | verdict |
|---|---|---|
| **Public Health Professional** | "population *retail*"? Meaningless. | Health is **constitutive** → Sector 4, even though the skill is statistics and programme management |
| **Medical Coder** | Motor-insurance claims — same job, same rulebook | Health was **incidental** → removed from Sector 4, roles routed to 5 and 6 with an HSSC tag |
| **Hospital Administrator** | Running a hotel, a factory, a school | Management is the skill → Sector 5, tagged HSSC |
| **Veterinary Doctor** | Cannot swap — the patient *is* the work | Health, of animals → Sector 4 |

Public Health Professional is the case that proves the rule: **no technical clinical skill, and it
still belongs**, because a student who cares about health and not about touching patients is a real
student and this is their profession.

Worked through:

| pair | interest | skill set | verdict |
|---|---|---|---|
| Electrician vs Electrical Engineer | similar | **different** — wiring vs power system design | **both stay** |
| Automobile Mechanic vs Mechanical Engineer | similar | **different** — repair vs design | **both stay** |
| Automobile Engineer vs Mechanical Engineer | different | **same** — thermodynamics, mechanics, CAD | **MERGED** |
| Solar Panel Technician vs Electrician | similar | **same** — electrician plus a specialisation | **MERGED** |

The reason a shared skill set forces a merge is concrete: **two professions with the same skill
profile will always surface together in a psychometric recommender**, adding noise without
information.

Merges are recorded in a `merged_into` block, which is **not** the same as `routed_elsewhere` —
a routing points at another sector and is reconciled across files; a merge points inside the
same sector and is not.

## 9. `admin_review` — where judgment alone isn't enough

`verification.status` says whether a fact was **fetched**. `admin_review` says whether a
human should **decide**. Different questions — a record can be `judgment` and perfectly
safe, or `verified` and still need a human call.

```json
"admin_review": { "required": true, "priority": "high", "reason": "..." }
```

Flag `required: true` when any of these hold:

1. **The claim could steer a student wrong at real cost** — a volatile market, or a career that may not be durable.
2. **A tier assignment was contestable** and going the other way changes the recommendation.
3. **A number is a wide guess** — most salary bands, but flag the ones where the spread is largest.
4. **The framing needs a human eye** for a school-age audience.
5. **A verified fact has known variation we haven't checked** — e.g. state-level lateral entry caps.

`priority` is `high` / `medium` / `low`. `reason` is mandatory when `required` is true — the validator enforces it.

`python tools/export_csv.py` prints the queue, highest priority first. Sector 1: **8 of 17 flagged** — 3 high, 5 medium.

Expect this ratio to *fall* in regulated sectors, where a statutory body settles most questions, and to stay high in emerging or unregulated fields.

---

## 10. Correction on record

The README originally listed NCS, India Skills Report, NID, Sangeet Natak Akademi, Institution of Engineers, TERI and ICAR as "Sources." **None had been opened.** That list was carried over from the brief as though it were a bibliography. Fixed — the README now distinguishes *consulted* from *not yet consulted*.

All Sector 1 professions, job roles, tiers and tags were produced by reasoning, not fetched. They are marked `judgment` accordingly.

**Second correction.** The JEE attempt window was initially described as making engineering a "hard block" for anyone more than ~3 years out of school. That was wrong — B.Tech lateral entry from a diploma or a B.Sc carries no national age cap. The exam expires; the profession does not. This error is what produced the `entry_window` design in §4.3, where limits attach to routes rather than to professions.

**Fifth correction — invented statutory body names.** Sector 4 named nine NCAHP professional councils. The fetched source named only *two* of them; the other seven were written from plausibility. Three did not exist at all — "Renal Care Professional Council", "Emergency Medical Professional Council" and "Operation Theatre Professional Council". A statutory body's name is a fact, not a phrasing choice. Corrected in Sector 4 v1.2 against the statutory list of ten categories.

**Sixth correction — unsourced money marked verified.** All 20 Sector 4 `economics` blocks claimed `status: "verified"` citing the NEET eligibility page and the UGC list of professional councils. **Neither page contains a single rupee.** The build script had pasted the *eligibility* verification block onto the *economics* block, and both tools passed it because each checked only that a source string was present. All 20 downgraded to `judgment`.

This produced the `money_sources()` check in `audit.py`: **a compensation figure may not cite a source registered in `verified_facts.json` unless that fact itself states money.** The CSIR JRF page is exempt — it is registered as an eligibility fact but does state the stipend. The check is why the rule "never invent a number" now has teeth; before this, a number only had to *look* sourced.

**Seventh correction — an industry mistaken for a sector.** Medical Coder shipped inside a locked Sector 4. Interest alignment pointed at healthcare, but the *skill set* is classifying documents against a published rulebook — the same skill as insurance claims processing. Healthcare was only the industry the documents came from, and §2 already says to push an overlap **down to the industrial tag, never up into a sector**.

Every field on the record said so and none was read against the others: `class12_prerequisite: "any"` in a sector where 18 of 20 demanded PCB; `industrial_sectors` carrying BFSI and IT-ITES beside HSSC; `skill_physical: 0`; the only null `licensing_body` among the clinical records. It also failed the demand-side profession test of §8.95 on the skill-set half, and it was not really one profession at all — six job roles across two different skill families.

Removed and split into two `routed_elsewhere` promises, to be absorbed **as job roles**: coding, billing and claims to Sector 6; records and documentation to Sector 5.

Two rules come out of it, both now in CLAUDE.md:

1. **The sector is set by the skill set, not the industry.** Test: would this person's skills transfer to another industry unchanged? If yes, the industry is a tag.
2. **A coverage gap may not justify a placement.** Medical Coder was partly kept because it was one of the only non-PCB doors into healthcare. That reasons backwards from a gap to a category. A sector is allowed to be closed to some students if the work really is closed — clinical work does require biology.

**Eighth correction — we wrote the trap ourselves.** Both this document (§8.4) and
`filter_rules.json` asserted that Mason "repays in 0.09 years **while trapping you at 3.0 LPA for
life**." The claim was false, it appeared in two files, and its cause was a rule three lines above
it: `mid_career_lpa` is **employed-only by design**, which deletes exactly the half of the income
where the trades win. All 8 building trades are `self_employment: common` — the mason who becomes a
contractor, the electrician with a shop.

It surfaced from an unrelated question: why the trades read as low-status to aspirational students.
The answer was that they read as dead ends **in our own data**, and we had put them there. A
prejudice we were being asked to accommodate turned out to be partly a defect we had authored.

Fixed by making `self_employment` an object carrying `ceiling_lpa` and `route` (§8.7b). Only 3 of
45 ceilings could be sourced; the rest are `null` with an `admin_review`, because a number that
cannot be sourced is **owed, not absent**. The counter-fact is recorded alongside so the fix does
not become a new falsehood in the other direction: Indian self-employed workers average about
₹13,200 a month against ₹21,000 salaried. **The ceiling is a ceiling, not an expectation.**

**Ninth correction — a lock marker that lied.** All four sector files carried
`{"status": "LOCKED", "date": "2026-08-06"}`. No tool ever read it, and all four sectors changed
after that date — Sector 4 four times. Removed everywhere. Version number and `changelog` already
carried the truth; the marker only contradicted it.

**Tenth correction — the spec documented a schema the data never used.** §4.3 showed `entry_window`
as `constrained_routes[]` and `open_routes[]`, arrays of objects. Every record ever written used
`constrained_route` and `bypass`, plain strings. The two never matched, and `spec_drift()` could
not see it because it compares **top-level profession keys** against the §1 table and never looks
inside a nested object.

The same section also predicted hard blocks in Sector 7 that turned out not to exist — state PSCs
and CDS/AFCAT both provide real bypasses.

Fixed by rewriting §4.3 to the shape in use and pinning `ENTRY_WINDOW_KEYS` in `export_csv.py`, so
a nested shape can now drift only once before something catches it. **The lesson generalises: a
documentation check that only compares key NAMES will miss every disagreement about key SHAPE.**

**Eleventh correction — field names that lied.** `entrance_exams.national` held state PSC, state
police, state nursing, state pharmacy, state judicial and state fire-service exams — seven distinct
entries across fifteen professions. `entrance_exams.private_reputed` held NISM registration (a SEBI
requirement), CFP and the Insurance Institute examinations (professional certifications, not
entrances), and CUET (LLB) — a **public** central-university test sitting in the private list.

The drift was invisible because nothing validates what a *name* implies about its *contents*.
Renamed to `public_routes` and `private_entrances`, the three certifications evicted to
`path_to_entry` where each was already recorded, and CUET (LLB) moved to the public side.

**Twelfth correction — a coverage gap standing in for a judgment, in the other direction.**
Sector 1's Game & Interactive Media Developer carried **Game Designer** and **Level Designer** as
job roles, because no design sector existed yet. That is the §2.06 error inverted: not reasoning
from a gap *to* a placement, but parking work in the nearest built sector *because* its real home
was unbuilt.

The evidence was already inside the record and had been for sixteen versions. Its `role_spread`
flagged exactly those two roles as deviating on `openness`, `existential` and `verbal`, with the
note *"same profession, opposite temperaments."* **Opposite temperaments inside one record is
usually two professions.** `role_spread` turns out to be a boundary detector as well as a
psychometric one — a wide spread whose deviating group shares an object of concern different from
the rest is a split waiting to be made.

Caught by `duplicate_job_roles()` when Sector 8 claimed the same two titles. Fixed by moving both
to Sector 8, where Game Designer is now a profession; Sector 1 keeps the engineering roles and
gains a `routed_elsewhere` entry. **Asked before editing a built sector, and approved** — the
build prompt's hard constraint working as intended.

**Thirteenth correction — a sector written in isolation priced itself above the ones it sits
beside.** Sector 8's first pass had UI/UX Designer at 18.5 LPA, Game Designer at 17.0, Industrial
Designer at 16.0 and Advertising Creative at 15.5 — **all above Software Developer at 14.0.** In
India a software developer out-earns a designer at 5–8 years at almost every employer, so the set
was wrong even though each figure looked defensible alone.

Nothing automated could catch it: every block passed `check_economics`, because internal
consistency is all it tests. **A number can be individually valid and collectively false**, which
is precisely what the cross-sector iteration exists for, and it is the first time that pass has
paid for itself. Six blocks re-based.

**Fourteenth correction — `routed_elsewhere` means two different things depending on whether the
target is built.** Sectors 9 and 10 each wrote a routing note pointing at an *already built*
sector: "Media Sales & Advertising Executive → Sector 5" and "Talent & Artist Manager → Sector 5."
Both read as sensible boundary notes. Both failed `reconcile()`, and correctly.

The distinction the field silently carries:

| target | what the entry means |
|---|---|
| **unbuilt** sector | a **promise** — "put this there when you build it" |
| **built** sector | an **assertion** — "this is already there," and the validator checks it |

So a routing note aimed at a built sector is only legal when that sector genuinely contains the
thing. When it does not, what you have found is **a coverage gap, not a routing decision**, and it
belongs in `boundary_decisions_needing_your_signoff` where a human sees it — because closing it
means amending a built sector, which requires asking.

Talent & Artist Manager is now recorded there: it survives the substitution test as management,
which points at Sector 5, and Sector 5 is finished and does not contain it.

**Fifteenth correction — punctuation is not part of a word.** `reconcile()` reported Sector 7's
promise of "Teacher (government school)" to Sector 12 as **broken**, when Sector 12 lists
**Government School Teacher** and the promise was plainly kept. The matcher split the promise on
whitespace and produced the tokens `(government` and `school)`, neither of which appears in any
honest job title.

Fixed by stripping non-alphanumerics from both the promise and the candidate entries before
comparing. This is the same class of defect as the slash fix already recorded in that function —
**the matcher kept inventing tokens that no real title could contain**, and every such invention
is a false BROKEN report that pressure-tests a human into renaming good data to satisfy a bug.

The general rule this pair establishes: when a validator says the data is wrong, check the
validator's *tokeniser* before changing the data. Two of the three reconciliation failures found
across Sectors 8–12 were the tool's fault, not the record's.

**Sixteenth correction — the salary format does not fit six professions, and it is now a pattern
rather than an exception.** `mid_career_lpa` is EMPLOYED-ONLY by design (§8.4), which was the right
call when the dataset was engineering and medicine. Across Sectors 9–12 it has failed repeatedly,
in two distinct shapes:

| shape | records |
|---|---|
| **no employed version exists at scale** — income is per performance, session, booking or student | Musician · Dancer · Folk Performer · Instrument Maker · Theatre Practitioner · Sports Official |
| **power-law income a range misrepresents** | Entrepreneur (S5) · Digital Content Creator (S9) · Actor (S10) · Professional Athlete (S11) · Esports Professional (S11) · Coaching Faculty (S12) |

Both were already known singly — Entrepreneur was flagged in Sector 5 and Sector 4's bimodal pay
is still open. What is new is that they are **structural**, not per-record oddities: six sectors
have independently arrived at the same request. This is a **schema decision** and is recorded here
rather than fixed, because inventing a second money format mid-build is exactly the kind of
unilateral change the build contract forbids.

**Seventeenth correction — a subject gate that deleted students the exam does not exclude.**
Environmental Engineer (S14) and Agricultural Engineer (S15) both carried
`class12_prerequisite: ["physics","chemistry","maths"]` behind a `jee-main` gate. But
`verified_facts.json#jee-main-paper1-btech`, already in this repo, says JEE Main Paper 1 requires
**Physics and Maths compulsorily plus any one of Chemistry, Biology, Biotechnology or a technical
vocational subject.** Every one of the fifteen JEE-gated B.Tech records in Sector 2 correctly uses
`["physics","maths"]`; only these two did not.

This is not cosmetic. §8.5 lists `class12_prerequisite` as a **hard filter that removes**. A
Physics + Maths + Computer Science student was being deleted from two professions they are eligible
for. **An over-restrictive gate is the dangerous direction of error**: a gate that is too loose
shows a student something they must then check, while a gate that is too tight shows them nothing
at all and they never learn it was open. Found twice in this build — Sector 15's Agricultural
Scientist and Food Technologist had the same defect with PCB.

**Eighteenth correction — a household figure verifying an individual one.** Farmer (S15) marked its
economics `verified` against the NSS 77th round Situation Assessment Survey. That survey gives
₹10,218/month for an agricultural **HOUSEHOLD** — about 1.23 lakh a year for a whole family, of
which only ₹3,798 is cultivation. The record asserted an individual mid-career midpoint of **1.8
lakh**, which is *more than the entire household earns in the cited source*.

`money_sources()` could not catch it, because the source genuinely does contain money — the check
it would need is a **units** check, and no tool has one. This is the sixth correction's shape in a
new disguise: not "verified against a page with no money", but **"verified against money that
measures a different thing."** Downgraded to `judgment`; the excellent existing nuance stating the
household problem is kept, and the `admin_review` now names which number the source does support.

**Nineteenth correction — the entry_competition reflex, six times.** Across Sectors 13, 15, 16 and
10 a `primary_gate` was set to the most **famous** exam a profession touches rather than the most
**decisive** one: CUET for Social Worker, CAT for Development Professional, IBPS PO for
Agri-Business, NCHMCT JEE for Chef **and** for Hotel & Restaurant Manager, NSD for Actor.

All six records argued against themselves in their own text — Chef's `entrance_exams.note` said
"most working Indian chefs sat neither", Actor's nuance said "almost none do", Hotel Manager was
`after_any_degree` behind a 12,000-seat exam. **When a record contradicts its own gate in prose,
the gate is wrong.** That is now the cheapest available check for this error and it should be run
before the registry is consulted at all.

The underlying pull is worth naming: a quantified gate looks like rigour. Recording a famous number
*because it is the only number available* is the opposite of what the registry is for — the
registry exists to say what a student is walking into, and 26 NSD places a year is not what an
actor is walking into.

**Twentieth correction — a meaningless number was deciding visibility.** Six records
(Entrepreneur, Digital Content Creator, Actor, Professional Athlete, Esports Professional,
Coaching Faculty) each carried a nuance saying their income is a power law that a range
misrepresents. Meanwhile `mid_career_midpoint` — computed from that very range — continued to drive
the derived `filter` boolean, which decides whether a profession is **shown at all**.

So the dataset was simultaneously asserting *this number means nothing* and *this number decides
whether a student ever sees this career*. It took six sectors independently arriving at the same
complaint before the contradiction was visible, because each looked like a one-off presentation
gripe rather than a structural fault.

Fixed with one enum, `economics.distribution` (§8.4). It invents no numbers and adds no second
money format, and it closed three separately-recorded problems at once: the six power-law records,
School Teacher's KVS-versus-private gap, and **Sector 4's bimodal pay-and-cost question, open since
Sector 4 was built.**

**The generalisable lesson: when several records independently ask for the same exception, the
schema is wrong, not the records.** The pattern was in the `nuances` field the whole time — a
nuance is meant to record something *settled*, so six nuances describing an unsettled problem was
itself the signal.

**Twenty-first correction — a verified fact with no profession behind it.** `verified_facts.json`
carried `jee-main-paper2b-bplan` — "JEE Main Paper 2B (B.Planning) requires Mathematics in class 12;
Physics and Chemistry are not required" — and §4 used B.Plan as its **worked example** of the
`class12_prerequisite` rule. **No profession in any of the eighteen sectors consumed it.** Somebody
had gone and verified a fact for a career the taxonomy did not contain, and nothing noticed for
eleven sectors.

The cost was not academic. B.Planning is one of the very few routes into the built environment that
needs **Maths alone** — no Physics, no Chemistry. A commerce student with Maths can enter it when
B.Arch and B.Tech are both shut to them, and the dataset was silent on that door while quoting the
rule that describes it.

**A verified fact is a claim that somebody needed this.** An orphaned one is a profession-shaped
hole with a receipt attached, and it is the cheapest possible signal of a coverage gap — cheaper
than the substitution test, cheaper than a reviewer. `audit.py` now checks for it — `orphaned_facts()`.

**The first thing it caught was not a missing profession but a missing citation.**
`#barch-eligibility` was orphaned while Architect carried the exact PCM gate the fact establishes.
The record was right and uncited: the source for *why Physics is compulsory* lived only in the
facts file, so nothing tied the claim to its evidence. Now a nuance on `class12_prerequisite` does
(S2 v20.1). **An orphaned fact has two possible causes — a profession that is missing, or a
profession that is not citing its evidence — and the second is the more common one.** Five remain
orphaned and are genuinely unused: `jee-main-attempt-window`, `amie-iei-recognition`,
`nsdc-sector-skill-councils`, `cat-mba-eligibility`, `icar-aieea-fifteen-percent`.

**Twenty-second correction — office is not licence, and treating it as one produced a false Tier
A.** Judicial Services Officer (S7) named the **Bar Council of India** as its `licensing_body` and
was Tier A. A judge does not practise under a BCI licence: an advocate who takes full-time service
is moved to the **non-practising list and surrenders their enrolment certificate**, and the BCI has
no power to strike off a judge. BCI enrolment is a prerequisite for *eligibility* — a
`path_to_entry` step — not a licence.

**This is now a standing rule — §7.1.** The test that settles it: **is there an unlicensed version of this work to
police?** You can practise medicine or law without a licence, illegally, which is what makes NMC
and BCI licensing bodies. **You cannot practise as a judge without being appointed one.** Where no
unlicensed version can exist, the licensing frame does not apply and the profession is an *office*.

The correct model was already in the same file, three times over — Civil Services Officer, Police
Officer and Armed Forces Officer are all `undergrad` / `licensing_body: null` / Tier B /
`legal_accountability: true` with a statutory-office nuance. **Judicial Services was the lone
outlier in its own sector and nothing caught it for two versions**, because every automated check
it touched was satisfied: it *had* a licensing body, it *was* verified, and the source page was
real. Only the question "is this body actually the licensor?" would have caught it, and no tool
asks that.

A related coupling is now known to be too tight and is **not** changed here: `audit.py` requires
`degree_dependency: "professional"` to name a licensing body. That holds for every professional
degree in the dataset so far because they all lead to licensed practice — but an LLB leading to
judicial office is the first counter-example, and the record is `undergrad` partly to satisfy a
validator rather than purely on the merits. Flagged rather than fixed.

**Twenty-third correction — the compensation filter was cutting careers on a number the record
itself called incomplete.** 23 of 218 professions failed the filter, and **21 of the 23 had LOW AI
exposure**. Mean AI exposure of what shipped was 32.2; of what was cut, 14.7. The filter was
systematically deleting the most AI-proof half of the taxonomy.

The cause was not the 4.5 threshold. It was that `mid_career_midpoint` **excludes business
ownership by design** — `filter_rules.json` → `known_limitations` had said so in writing since v1.0
— and the filter ran on it anyway. On a mason, a tailor, a weaver or a farmer, that midpoint is a
floor somebody *leaves*, not a ceiling they hit.

**The exemption, and why it is not a loophole:** `self_employment.likelihood == "common"` **AND**
`admin_review.required`. Both are needed. `common` alone would spare records whose figure is simply
low; `admin_review` alone would spare employees with no ownership path at all. Together they mean
one thing only — *the record has already written down that this number is missing.* Which is the
same principle as the `power_law` exemption: **do not filter on a figure the record has declared
incomplete.** Both are self-closing: source the owner figure, the `admin_review` closes, and the
profession re-enters the filter on the next run. 23 cuts → 12.

**Two things this correction got wrong on the first attempt, and both matter more than the fix.**

1. **It exempted Website & Online Store Builder** — self-employed, owes an owner figure, and scores
   72 on AI exposure. The AI penalty clause was written *for that exact record*. A blanket
   exemption would have cancelled the clause through the back door. So the exemption applies to
   **the pay floor only, never the AI clause**: ownership answers *"is this figure the whole
   income"*, and says nothing about *"is this work disappearing"*.
2. **It was described as rescuing Automobile Mechanic, and it does not.** Automobile Mechanic is
   what *revealed* the gap — cut at 4.25 with a self-employment ceiling of 6–18 lakh — but that
   ceiling is **sourced**, so the record owes nothing, carries no `admin_review`, and stays cut.
   The exemption covers records where the owner figure is **missing**, not records where it is
   present and high. The honest fix for Automobile Mechanic is to raise the floor or filter on the
   ceiling — not to widen this rule until it swallows the case that inspired it.

**The general lesson: an exemption written from one motivating example will over-fire.** Check it
against the record the original rule was written to catch, not only against the records you want
rescued.
