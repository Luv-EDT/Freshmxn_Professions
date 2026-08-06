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
| `entrance_exams` | `{ national: [], private_reputed: [], note }` — cap private at ~5 genuinely reputed |
| `entry_window` | time limits on routes, `null` if none. See §4.3 |
| `licensing_body` | statutory body, `null` if unregulated |
| `years_to_qualify` | typical years from class 12 to first job |
| `economics` | `{ cost_of_entry_lakh, early_earnings_lpa, mid_career_lpa, mid_career_midpoint, payback_years, basis, verification }` — see §8.4 |
| `demand_signal` | `{ india_demand, pathway, note? }` — see §8.45 |
| `filter` | **derived** boolean. True = passes the compensation rule in `filter_rules.json`. See §8.5 |
| `after_undergrad` | `masters_required` / `masters_is_the_entry` / `masters_advantage` / `work_first` — see §8.7 |
| `self_employment` | `common` / `possible_later` / `rare` |
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
years while trapping you at 3.0 LPA for life. Ranking by payback would put masons first. It is kept
because it correctly isolates capital risk, which for Commercial Pilot (4.07 years, 57 lakh self-funded)
is the whole story.

**All wage figures come from commercial salary aggregators, not government data.** India has no
authoritative free source for occupational earnings. This is the single largest known weakness.

## 2. The 18 professional sectors are fixed

Single parent. No profession in two sectors. **Overlaps push down to industrial tags, never up.**

- Teaching-anything → Sector 12, whatever the subject.
- Empirical research → Sector 3. Interpretation/heritage → Sector 17.
- **Method decides, not discipline.** Empirical and quantitative work goes to Sector 3 even when the subject is social — research psychology and demography sit there. Ethnography and cultural interpretation go to Sector 17. The discipline label is not the test.
- **Intervene vs interpret** splits Sector 13 from Sector 17. A counsellor changes wellbeing (13). A historian explains it (17).

### 2.1 Sector 7 boundary

Three families: **Law & Justice** (lawyer, judge, prosecutor) + **Civil & Administrative Services** (IAS, IPS, IRS) + **Policy & Diplomacy**.

> Only careers whose work **exists because the state or justice system exists.** A profession that merely works *for* government stays in its home sector with a Government industrial tag.

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

Some entrance exams expire. **JEE Main 2026 admits only 2024/2025 passouts and 2026 appearers** — roughly a 3-year window from class 12.

**A profession is blocked only when every route is blocked.**

Engineering is the worked example, and it is *not* blocked. JEE closes, but a 3-year diploma leads to lateral entry into B.Tech year 2 with generally no upper age limit, and B.Sc graduates are eligible for lateral entry too.

```json
"entry_window": {
  "constrained_routes": [
    { "route": "JEE Main Paper 1", "max_years_since_class12": 3,
      "fact": "data/verified_facts.json#jee-main-attempt-window" }
  ],
  "open_routes": ["3-year diploma then lateral entry into B.Tech year 2", "B.Sc lateral entry"],
  "is_hard_block": false
}
```

**Engine rule:**
- `null` → no time constraint
- `is_hard_block: false` → narrow the route, **show the bypass**, never exclude
- `is_hard_block: true` → exclude, and say why

The validator rejects `is_hard_block: false` with no `open_routes`, and `true` with any `open_routes`. That contradiction is exactly the error made when this was first raised: an expiring *exam* was read as a closing *profession*. Real hard blocks are expected in Sector 7 — NDA and UPSC carry genuine statutory age caps with no bypass.

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

---

## 8.45 `demand_signal` — demand and pathway are different questions

Conflating them is an error made and corrected here. Biomedical Engineering was nearly written off because
Indian degrees underdeliver — but India **imports** most medical devices, which is evidence of demand, not
its absence. A weak pathway is a supply problem, not a demand problem.

- **`india_demand`** — `high` / `moderate` / `low`. Does society need this work?
- **`pathway`** — `india` / `any` / `abroad`. Where can you realistically train for it?

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
> **interest alignment + a separate skill set**, containing multiple job roles.

Both halves are required. An earlier supply-side test — "distinct if reaching them requires a
different educational decision" — was **wrong**: it described how you get in, not what the work is.

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
