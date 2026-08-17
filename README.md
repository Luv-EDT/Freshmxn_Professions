# Profession Taxonomy — India Career Recommender

Structural profession list for Indian school and college students, across four journeys:
**class 9–10, class 11–12, college, early professionals.**

Psychometric factors, weights and `drivingReasons` are **not** in scope here — they attach later
via a separate pipeline keyed on `profession.id`. `data/psychometric_factors.json` holds only the
19-factor controlled vocabulary that `role_spread` is written against.

**[DECISIONS.md](DECISIONS.md) is the spec** — schema, scoring, boundary rules, verification
policy. **[.claude/CLAUDE.md](.claude/CLAUDE.md) is the working contract** — what to run, what never to do.
This file is orientation only.

## Layout

```
DECISIONS.md                    the spec — read before touching data
.claude/CLAUDE.md               the working contract
data/
  professional_sectors.json     18 fixed parents + the cross-cutting employer rule
  industrial_sectors.json       NSDC 38 Sector Skill Councils + 8 EXT- extension tags
  psychometric_factors.json     the 19-factor vocabulary role_spread must use
  verified_facts.json           every fetched fact, with source and date — fetch once, reuse
  filter_rules.json             compensation thresholds AND preference presets. The only
                                place filter logic lives.
  entrance_gates.json           competition and seats per EXAM, shared across professions
  professions/NN-<sector>.json  one file per professional sector
tools/
  validate.py                 per-field validation + CSV export
  audit.py                      cross-field consistency + cross-FILE reconciliation
  probe.py                      is this candidate already covered? Run BEFORE adding anything.
build/ALL-professions.json      all 18 sectors in one LOSSLESS file, nested structures
                                intact. Generated; the per-sector CSVs were removed.
```

## Workflow

```bash
python tools/validate.py                        # validate + export, all sectors
python tools/validate.py 01 03                  # just those
python tools/audit.py                             # cross-field + cross-file
python tools/probe.py "<name>" <defining skills>  # before adding a profession
```

**Both tools must be clean before any change ships.** They check different things: `validate`
checks each field is legal on its own, `audit` checks the fields agree with each other. Real
errors hide in the second — it has caught three wrong verification tiers, a whole missing
profession, invented statutory body names, and a merge filed in the wrong sector.

`probe.py` also reads the **graveyard**: professions already routed away or merged. It answers
"this was considered and deliberately not kept" rather than "genuinely new", so a recorded
decision is not silently reversed.

### Blocks carried by every sector file

- `routed_elsewhere` — professions a reviewer expects here and won't find, with where they went
  and why. `audit.py` reconciles these: an unkept promise is an error once the target is built.
- `merged_into` — same-sector merges. Not reconciled; a merge is not a routing.
- `boundary_decisions_needing_your_signoff` — judgment calls that could have gone the other way.
- `changelog` — every version, including every correction. Deleting one deletes the why.

## Two things this repo will not do

**No invented numbers.** No salary, fee or wage figure without a fetched source. Commercial
aggregators disagreed by 4–5× on the same Indian profession, so where statutory pay exists — 7th
CPC matrices, published fee schedules — that is the anchor, and the private-sector reality goes
in a `nuance` beside it.

**No field that ranks social status.** A `societal_tier` was requested and rejected; the factual
substitute `employment_formality` was designed and also rejected, because it classes a funded
startup founder and a daily-wage mason both as `informal`. Aspiration is served by a **query** —
`filter_rules.json` → `preference_filters` — never by a column. See DECISIONS.md §8.7b.

## Sources

Every fetched fact is in `data/verified_facts.json` with its source and date — **34 facts** and 13 entrance gates so
far. Highlights: NEET, JEE and CAT eligibility · NMC and NCAHP registration · the ten NCAHP
councils · DGMS certificates of competency · DG Shipping MEO Class IV sea time · ISRO's GATE
route · AIIMS 7th CPC pay levels · ICAI, ICSI and Bar Council routes · UPSC age and attempt limits · the Actuaries Act · UGC's list of statutory professional councils.

### Named in the brief, NOT yet consulted

NCS (National Career Service) · India Skills Report · NID · Sangeet Natak Akademi ·
Institution of Engineers (India) · TERI · ICAR · NCO 2015 · NSDC QP-NOS.

Opened as the sectors that need them come up — ICAR for Sector 15, NID and Sangeet Natak Akademi
for Sectors 8 and 10.

> An earlier version of this file listed all of the above under "Sources" as though they had been
> used. They had not. That is correction #1 of nine on record in DECISIONS.md §10.

## Status

| # | Professional sector | Professions | Verified | Version |
|---|---|---|---|---|
| 1 | Software & Computing | 14 | 1 | v16.1 |
| 2 | Engineering & Making | 37 | 35 | v20.5 |
| 3 | Science & Research | 19 | 7 | v7.1 |
| 4 | Healthcare & Medicine | 20 | 17 | v2.0 |
| 5 | Business, Management & Entrepreneurship | 13 | 0 | v1.2 |
| 6 | Finance & Economics | 8 | 2 | v1.1 |
| 7 | Law, Governance & Public Service | 11 | 7 | v1.2 |
| 8 | Design & Creative Arts | 15 | 0 | v1.1 |
| 9 | Media, Film & Storytelling | 12 | 0 | v1.1 |
| 10 | Performing Arts & Music | 10 | 0 | v1.2 |
| 11 | Sports & Fitness | 8 | 0 | v1.1 |
| 12 | Education & Training | 10 | 3 | v1.1 |
| 13 | Social Impact & Psychology | 8 | 1 | v1.1 |
| 14 | Environment & Sustainability | 8 | 0 | v1.3 |
| 15 | Agriculture & Food Systems | 8 | 0 | v1.3 |
| 16 | Hospitality, Travel & Culinary | 7 | 0 | v1.3 |
| 17 | Humanities, Culture & Belief | 9 | 1 | v1.1 |
| 18 | Personal Care & Wellness | 6 | 1 | v1.2 |

**223 professions · 1716 job roles · 438 nuances · 59 verified facts · 56 profession-level and 15 sector-level admin reviews open.**

The verified/judgment ratio is a property of the sector, not of the effort spent. **Sector 1 is
1 of 14, and Sector 5 is 0 of 12, because nothing in computing or in Indian general management is
statutorily licensed** — no Tier A authority
exists to check against. Sector 4 names 17 statutory licensing bodies. Sector 2 sits between.

There is no `LOCKED` marker. There was one, and it lied — all four sectors were stamped locked on
2026-08-06 and all four changed afterwards. A sector is finished when both tools are clean and
every key has had two review passes; **finished does not mean frozen.**
