# Profession Taxonomy — India Career Recommender

Structural profession list for Indian school and college students. Psychometric
factors, weights and `drivingReasons` are **not** in scope here — they attach later
via a separate pipeline keyed on `profession.id`.

**[DECISIONS.md](DECISIONS.md) is the spec.** Schema, scoring model, boundary rules and
verification policy all live there. This file is orientation only.

## Layout

```
DECISIONS.md                    locked design decisions — read this first
data/
  professional_sectors.json     18 fixed parents
  industrial_sectors.json       NSDC 38 Sector Skill Councils + EXT- extension tags
  verified_facts.json           eligibility facts fetched from source, reused across sectors
  professions/
    01-software-and-computing.json
    02-... (one file per professional sector)
tools/
  export_csv.py                 JSON -> per-sector CSV, plus validation
build/
  *.csv                         generated, not hand-edited
```

## Review workflow

```bash
python tools/export_csv.py            # all sectors built so far
python tools/export_csv.py 01         # just one
```

Writes `build/<nn>-<sector>.csv`, one row per profession, list fields joined with `|`.
JSON stays the source of truth. The script also fails loudly on unknown industrial tags,
illegal enum values, unknown class-12 subjects, missing verification blocks, and any
Tier A profession that claims `judgment` instead of `verified`.

Each sector file also carries:

- `routed_elsewhere` — professions a reviewer will expect to find there and won't, with
  the sector they actually went to and why. The audit trail for the single-parent rule.
- `boundary_decisions_needing_your_signoff` — judgment calls that could reasonably have
  gone the other way.

## Sources

### Actually consulted

- [National Skills Network — Sector Skill Councils](https://nationalskillsnetwork.in/sector-skill-councils/) — the 36 published SSC names
- [NSDC — Sector Skill Councils](https://nsdcindia.org/sector-skill-councils) — confirms 38 approved; page served no list
- [Careers360 — JEE Main eligibility](https://engineering.careers360.com/articles/jee-main-eligibility-faqs) — class 12 subject requirements and the attempt window
- [Neram Classes — B.Arch eligibility, CoA norm](https://neramclasses.com/counseling/concepts/eligibility-45-vs-50-rule) and [AFD India — NATA/B.Arch](https://afdindia.com/blog/post/nata-barch)

Everything fetched is recorded with a date in `data/verified_facts.json`.

### Named in the brief, NOT yet consulted

NCS (National Career Service) · India Skills Report · NID · Sangeet Natak Akademi ·
Institution of Engineers (India) · TERI · ICAR · NCO 2015 · NSDC QP-NOS.

These will be opened as the sectors that need them come up — IEI for Sector 2, ICAR for
Sector 15, NID and Sangeet Natak Akademi for Sectors 8 and 10.

> An earlier version of this file listed all of the above under "Sources" as though they
> had been used. They had not. Anything not fetched is marked `judgment` in the data, and
> `verification.status` on every record tells you which is which.

## Status

| # | Professional sector | Professions | Verified / judgment | State |
|---|---|---|---|---|
| 1 | Software & Computing | 17 | 1 / 16 | drafted |
| 2–18 | — | — | — | pending |

Sector 1 is almost entirely `judgment` by nature, not by neglect: **nothing in computing
is statutorily licensed in India**, so no Tier A authority exists to check against. Later
sectors — Healthcare, Law, Education, Architecture — invert this ratio.
