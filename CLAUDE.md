# CLAUDE.md

Profession taxonomy for an Indian career recommender. **[DECISIONS.md](DECISIONS.md) is the
specification — read it before touching data.** This file is the working contract.

## Before every change

```bash
python tools/export_csv.py    # per-field validation + CSV export
python tools/audit.py         # cross-field consistency + cross-FILE reconciliation
```

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
- **Never store a derived value without validating it.** `ai_exposure.band`, `exposure_raw`,
  `payback_years` and `filter` are all recomputed on every run.
- **Never present a legally contested qualification as a route.** AMIE is excluded sector-wide
  for this reason — post-2013 recognition is unresolved in the Delhi High Court.
- **Never use `degree_dependency` as an eligibility filter.** It is the destination, not the door.
- **Never add a seniority-tier profession or job role.** No Senior X, Head of Y, Chief Z.
  A profession is an entry identity, not a career ladder.
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
`verified_facts.json`, and in DECISIONS.md §10 if it changed the design. Four corrections are
on record so far. They are the reason several rules exist; deleting them would delete the why.

## Layout

```
DECISIONS.md                  the spec — schema, scoring, boundaries, verification policy
data/
  professional_sectors.json   18 fixed parents + the cross-cutting employer rule
  industrial_sectors.json     NSDC 38 SSCs + 8 EXT- extension tags
  verified_facts.json         every fetched fact, with source and date. Fetch once, reuse.
  filter_rules.json           compensation thresholds — the ONLY place these numbers live
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

Sector 1 is 1/14 verified because **nothing in computing is licensed in India**. Sector 4 is 20/20
with 17 statutory licensing bodies. That ratio is a property of the sector, not of the effort spent.

## Status

| # | sector | professions | verified | ships | state |
|---|---|---|---|---|---|
| 1 | Software & Computing | 14 | 1 | 13 | **LOCKED** v14 |
| 2 | Engineering & Making | 32 | 31 | 27 | **LOCKED** v15 |
| 3 | Science & Research | 19 | 7 | 19 | **LOCKED** v6 |
| 4 | Healthcare & Medicine | 20 | 20 | 20 | **LOCKED** v1.1 |
| 5–18 | — | — | — | — | pending |

**85 professions · 512 job roles · 66 nuances · 32 open admin reviews.**

`LOCKED` means both tools are clean and every key has had two review passes. It does **not**
mean the `admin_review` queue is resolved — those are decisions still owed by a human.

Sector 5 is Business, Management & Entrepreneurship.

## What a profession is

> A self-sufficient, easy-to-understand field a student can pursue, identified by
> **interest alignment + a separate skill set**, containing multiple job roles.

**Both halves required.** Same interest + same skill set ⇒ merge. Two professions with the same
skill profile always surface together in a psychometric recommender, adding noise without
information. That test merged Automobile Engineer into Mechanical and Solar Panel Technician
into Electrician.

Before adding anything: `python tools/probe.py "<name>" <defining skills>`. A new profession
costs economics, verification, AI scoring and review. A job role costs one line.
