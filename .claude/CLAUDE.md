# CLAUDE.md

Profession taxonomy for an Indian career recommender. **[DECISIONS.md](DECISIONS.md) is the
specification — read it before touching data.** This file is the working contract.

## Before every change

```bash
python tools/export_csv.py    # per-field validation + CSV export
python tools/audit.py         # cross-field consistency + cross-FILE reconciliation
```

**Check the EXIT CODE, not the printed output.** `export_csv.py` prefixes its errors with `!`,
not the word ERROR, so a text grep can read clean while the tool is failing. A stale rule
survived three whole sectors that way.

**Both must be clean.** They check different things: `export_csv` checks each field is legal
on its own; `audit` checks the fields agree with each other. Real errors hide in the second.
`audit.py` caught three wrong verification tiers on its first run, and a whole missing profession on its second.

`audit.py` also reconciles **cross-file promises**: if Sector 1 says a profession goes to Sector 3, Sector 3 must contain it once built. That check found Computer Science Researcher missing entirely.

## Review discipline — non-negotiable

**Every key of every profession gets reviewed at least twice. Three times if not convinced.**
This is why `audit.py` exists — the second pass is automated so it actually happens.

Prefer a script under `scratchpad/` for bulk edits over hand-editing JSON. Every derived value
is recomputed and rejected if it disagrees with its inputs.

## Never do these

- **Never invent a number.** No salary, fee or wage figure without a fetched source. If it
  can't be sourced, leave the field null and flag `admin_review`. Withdrawn once already for
  exactly this reason — families act on money numbers.
- **Never trust a commercial salary aggregator alone.** PayScale, Indeed, Glassdoor and
  SalaryExpert disagreed by 4–5× on the same Indian profession (optometrist: ₹33,400/yr to
  ₹14.2 lakh). Anchor on **statutory pay** where it exists — 7th CPC pay matrices, published
  fee schedules — and record the private-sector reality as a nuance beside it.
- **Never store a derived value without validating it.** `ai_exposure.band`, `exposure_raw`,
  `payback_years` and `filter` are all recomputed on every run.
- **Never present a legally contested qualification as a route.** AMIE is excluded sector-wide
  for this reason — post-2013 recognition is unresolved in the Delhi High Court.
- **Never use `degree_dependency` as an eligibility filter.** It is the destination, not the door.
- **Never add a seniority-tier profession or job role.** No Senior X, Head of Y, Chief Z.
  A profession is an entry identity, not a career ladder.
- **Never let the INDUSTRY or the SETTING decide the sector.** A sector is an *object of concern*
  — health, learning, justice — not an employer. Apply the **substitution test** (DECISIONS.md §8.95):
  swap the industry out; if the work survives unchanged, the industry is a tag. Medical Coder failed it
  (motor-insurance claims are the same job) and so did Biomedical Equipment Technician (calibration in
  a factory is the same job). Public Health Professional passes with *no clinical skill at all*, because
  remove health and nothing is left.
- **Never let a coverage gap justify a placement.** Medical Coder was kept in Healthcare partly
  because it was one of the only non-PCB doors into the sector. That is reasoning backwards from a
  gap to a category. A sector is allowed to be closed to some students if the work really is closed.
- **Never drop a profession for being low-paid, AI-exposed or oversupplied.** The only reason to
  drop is demand structurally collapsing through technological obsolescence — typewriter mechanic,
  stone tool maker. Everything else is a `demand_signal` value, a nuance, or a derived filter the
  application can reverse. `ai_exposure` speaks for itself; the app frames the warning.
- **Never add a field that ranks social status.** A `societal_tier` was requested and rejected —
  it encodes a caste-and-class hierarchy for 15-year-olds and, as a sort key, buries the most
  AI-proof careers we have. `employment_formality` was the factual substitute and **also** failed:
  it classes a funded startup founder and a daily-wage mason both as `informal`. Aspiration is
  served by a **query** — `filter_rules.json` → `preference_filters` — never by a column. §8.7b.
- **Never say preparation was worth nothing.** A failed UPSC or NEET attempt leaves no credential,
  but it leaves knowledge and adjacent routes. `entrance_gates.json` splits `credential_gained`
  from `transfers_to`, and `audit.py` rejects a gate whose `transfers_to` is empty. Misleading a
  family toward despair is as bad as overselling.
- **Never report competition odds without the cost.** A private gate is winnable at odds a public
  one is not, for a much larger fee. `typical_total_cost_lakh` is mandatory on private gates.
- **Never claim a source that was not opened.** The README once listed seven unconsulted
  sources as a bibliography. Fixed, and recorded in DECISIONS.md §10.

## `nuances` vs `admin_review`

> **`nuances` are SETTLED. `admin_review` is UNSETTLED.**

A nuance records something true we already know, where the tag alone misleads — e.g. Architect
names a `licensing_body`, but CoA registration protects the *title*, not the *activity*.
An `admin_review` records a decision a human still owes.

Every nuance must name a `field` that exists on the record, and must not hedge. The audit
rejects "not yet verified" / "needs verification" / "unverified" / "confirm before" inside a
nuance — that text belongs in `admin_review`. Both rules exist to stop `nuances` becoming a
free-text dumping ground.

## Corrections stay on the record

When something is found wrong, fix it *and* record it — in the sector `changelog`, in
`verified_facts.json`, and in DECISIONS.md §10 if it changed the design. Seven corrections are
on record so far (§10). They are the reason several rules exist; deleting them would delete the why.

## Layout

```
DECISIONS.md                  the spec — schema, scoring, boundaries, verification policy
data/
  professional_sectors.json   18 fixed parents + the cross-cutting employer rule
  industrial_sectors.json     NSDC 38 SSCs + 8 EXT- extension tags
  verified_facts.json         every fetched fact, with source and date. Fetch once, reuse.
  filter_rules.json           compensation thresholds + preference presets — the ONLY place
                              filter logic lives
  entrance_gates.json         competition, seats and preparation cost per EXAM, shared by the
                              professions behind it. Fetch once, reuse.
  professions/NN-<sector>.json
tools/
  export_csv.py               validate + export      tools/audit.py   cross-field audit
build/*.csv                   generated, never hand-edited
```

## Verification tiers

| tier | who controls entry | rule |
|---|---|---|
| **A** | a statutory body — practising without their licence is illegal | must verify; must name `licensing_body` |
| **B** | an entrance exam or admission rule | must verify |
| **C** | nobody — open market, no authority exists | `judgment`, and labelled as such |

Sector 1 is 1/14 verified because **nothing in computing is licensed in India**. Sector 4 names 17
statutory licensing bodies. That ratio is a property of the sector, not of the effort spent.

**A licensing body's name is a fact.** Verify the name itself, not just that a body exists — seven
NCAHP council names were written from plausibility and three of them did not exist (DECISIONS.md §10).

## Status

| # | sector | professions | verified | ships | version |
|---|---|---|---|---|---|
| 1 | Software & Computing | 14 | 1 | 13 | v16 |
| 2 | Engineering & Making | 32 | 31 | 27 | v19 |
| 3 | Science & Research | 19 | 7 | 19 | v7 |
| 4 | Healthcare & Medicine | 18 | 17 | 18 | v1.7 |
| 5 | Business, Management & Entrepreneurship | 12 | 0 | 12 | v1.0 |
| 6 | Finance & Economics | 8 | 2 | 8 | v1.0 |
| 7 | Law, Governance & Public Service | 10 | 7 | 10 | v1.0 |
| 8–18 | — | — | — | — | pending |

**113 professions · 712 job roles · 151 nuances · 34 verified facts · 14 open admin reviews.**

The 7 open items are all the same thing: a profession where going independent is normal, employed
mid-career is under ₹6 lakh, and **no sourced figure exists for what owners actually earn**. Until
it does, the record understates the profession.

The queue went 31 → 15 → **0**: six policy answers, then a research batch. Every closed item
became a `nuance` rather than a deleted ticket, which is why nuances went 66 → 105. One
sector-wide question is still open: **Sector 4 pay and MBBS cost are both bimodal, and one field
cannot say so.** That is a schema decision, not a fact to look up.

Sector 4 took **four** passes. Iteration 2 returned zero issues; iteration 3 found invented
statutory body names and 20 salary blocks marked `verified` against sources with no money in them;
the fourth caught Medical Coder sitting in the wrong sector entirely. Two clean passes are the
floor, not the ceiling.

A sector is **finished** when both tools are clean and every key has had two review passes.
**Finished does not mean frozen** — there is no lock marker, because there was one and it lied.
All four sectors were stamped `LOCKED` on 2026-08-06 and all four changed afterwards; Sector 4 was
corrected four times. That is the process working, not failing. The version number and the
`changelog` carry everything the marker pretended to.

Sector 8 is Design & Creative Arts. It owes the **apparel base layer** — Tailor, Garment Maker, Handloom Weaver — which no sector currently covers, for an industry employing tens of millions (DECISIONS.md §8.45).

## What a profession is

> A self-sufficient, easy-to-understand field a student can pursue, identified by
> **affinity for the sector's object of concern + a separate skill set**, meeting a **need that
> exists in society**, and containing multiple job roles.

**All three required.** Full worked version in DECISIONS.md §8.95.

**The need, not the degree.** A profession earns its place because society needs the work done —
not because an Indian degree for it exists. Chip designers count even though India imports its
chips; `demand_signal.pathway` carries that, not deletion. And a course existing is not evidence
of demand.

**The 18 sectors ARE the objects of concern.** Sector 4 is not "the healthcare industry", it is
**health**. That is why no third axis is needed: the sector carries the affinity,
`industrial_sectors` carries the employer.

**Same object + same skill set ⇒ merge.** Two professions with the same skill profile always
surface together in a psychometric recommender, adding noise without information. That test merged
Automobile Engineer into Mechanical and Solar Panel Technician into Electrician.

Before adding anything: `python tools/probe.py "<name>" <defining skills>`. A new profession
costs economics, verification, AI scoring and review. A job role costs one line.
