# Build Sectors 8–18 — specification prompt

Paste this whole file as a single prompt. It builds the eleven remaining professional sectors to
the standard the first seven were built to.

---

## What this project is

A **structural profession list for Indian students** across four journeys — class 9–10, class
11–12, college, early professionals. Psychometric factors, weights and `drivingReasons` are **out
of scope**; they attach later via a separate pipeline keyed on `profession.id`.

Every profession answers: what is this work, who can reach it, what does it cost, what does it pay,
how exposed is it to AI, and who says you are qualified.

**Where things stand: 7 of 18 sectors built · 113 professions · 712 job roles · 151 nuances ·
34 verified facts · 13 entrance gates.** Both tools exit 0.

| # | sector | professions | verified |
|---|---|---|---|
| 1 | Software & Computing | 14 | 1 |
| 2 | Engineering & Making | 32 | 31 |
| 3 | Science & Research | 19 | 7 |
| 4 | Healthcare & Medicine | 18 | 17 |
| 5 | Business, Management & Entrepreneurship | 12 | 0 |
| 6 | Finance & Economics | 8 | 2 |
| 7 | Law, Governance & Public Service | 10 | 7 |

---

## Read first, in this order

1. **`DECISIONS.md`** — the specification. Schema (§1), sector rules (§2), reachability (§4),
   scoring (§5), verification (§7), economics (§8.4), demand (§8.45), AI exposure (§8.6),
   self-employment and the no-status rule (§8.7b), nuances (§8.8), `role_spread` (§8.9), the
   profession test (§8.95), corrections on record (§10).
2. **`.claude/CLAUDE.md`** — the working contract and the never-do list.
3. **`data/professions/04-healthcare-and-medicine.json`** — the reference record shape.

---

## Hard constraints

> **Do not amend any existing rule, schema field, or built sector. If the work seems to require it,
> STOP and ask first, with the specific reason.** Adding a new profession to an unbuilt sector is
> not an amendment. Renaming a field, changing a threshold, moving a built profession, or relaxing
> a validator **is**.

- **Never invent a number.** No salary, fee or wage figure without a fetched source. Commercial
  aggregators disagree 4–5× on the same Indian profession — anchor on statutory pay (CPC matrices,
  published fee schedules) where it exists, and put the private-sector reality in a `nuance`. If it
  cannot be sourced, mark `economics.verification.status: "judgment"` with empty sources and open a
  `sector_admin_review`.
- **Never claim a source that was not opened.**
- **Never add a seniority tier.** No Senior X, Head of Y, Chief Z.
- **Never let the industry or the setting decide the sector.** Apply the substitution test (§8.95):
  swap the industry out; if the work survives unchanged, the industry is a tag.
- **Never add a field that ranks social status.** Aspiration is served by a query
  (`filter_rules.json` → `preference_filters`), never a column.
- **Never say preparation was worth nothing** — `entrance_gates.json` splits `credential_gained`
  from `transfers_to`.
- **Check the EXIT CODE, not the printed output.** `export_csv.py` prefixes errors with `!`.

---

## Per sector, in order 8 → 18

### Step 0 — inherited promises
Each sector already owes professions promised by built sectors. **Reconciliation fails until each
lands, as a profession or a job role.**

| sector | owed |
|---|---|
| **8 Design & Creative Arts** | UI/UX Designer · Animator/VFX Artist · Interior Designer · Industrial/Product Designer · Goldsmith/Bench Jeweller · Fashion & Apparel Production Technician · Advertising Creative/Copywriter |
| **9 Media, Film & Storytelling** | Technical Writer · Science Journalist · Medical Writer · Legal Journalist |
| **12 Education & Training** | Coding Instructor · Science Teacher/Professor · Corporate Trainer · Teacher (government school) |
| **13 Social Impact & Psychology** | Clinical/Counselling Psychologist ×2 · Genetic Counsellor · Social Worker |
| **14 Environment & Sustainability** | GIS & Remote Sensing Analyst · Environmental Engineer · Environmental Scientist |
| **15 Agriculture & Food Systems** | Agricultural Engineer · Agronomist · Food Technologist |
| **16 Hospitality, Travel & Culinary** | Cabin Crew · Merchant Navy Deck Officer · Hotel & Restaurant Manager · Event Manager |
| **17 Humanities, Culture & Belief** | Archaeologist · Anthropologist/Sociologist |
| **18 Personal Care & Wellness** | Yoga Instructor |

**Also close these standing base-layer gaps (§2.06):** apparel — Tailor, Garment Maker, Handloom
Weaver → 8 or 17 · agriculture — Farmer, Dairy Worker → 15 · hospitality — Cook, Steward,
Housekeeping → 16 · beauty — Beautician, Hair Stylist → 18 · healthcare — General Duty Assistant →
flag, Sector 4 is built. **Private security (~9M people) has no home** — it fails the Sector 7 test;
propose one and ask.

### Step 1 — verify before writing
Fetch the Tier A/B facts that govern the sector **first**, into `data/verified_facts.json`.
Expected authorities: Council of Architecture · NID/CEED · Sangeet Natak Akademi · RCI (clinical
psychology) · ICAR · FSSAI · IHM/NCHMCT · AICTE · state teacher eligibility (CTET/TET) · Bar-style
bodies where they exist. **A licensing body's name is a fact — verify the name itself.** Seven
NCAHP council names were once written from plausibility and three did not exist.

### Step 1b — populate `entrance_gates.json` for this sector

**`entrance_exams` says *which* exam. `entrance_gates.json` says *what a student is walking into*** —
how many compete, for how many places, over how long, and **what they hold if it fails.** Gates are
shared (22 professions sit behind JEE Main), so the numbers live once and professions reference
them by key. **Every sector adds its own gates as it is built.** Currently 13 gates, 9 pending.

```json
"entry_competition": { "primary_gate": "nid-dat", "alternative_gates": ["uceed"] }
```

**`primary_gate` is the gate that most DETERMINES whether you reach the profession — not the first
one you sit.** This was got wrong once: CUET was made primary for every research profession, which
told a would-be Physicist the hard part was getting into a B.Sc. It isn't — CSIR-UGC NET is, because
the JRF stipend decides whether a research career is financially survivable. 16 records re-pointed.

**`primary_gate` may be PRIVATE.** In animation, game design, culinary arts, sound engineering and
much of design there is no public entrance at all, and the private institute *is* the route. Type
does not decide precedence; decisiveness does. `alternative_gates` require a primary — a fallback
shown without the main route misleads — but if the alternative *is* the main route, promote it.

**Three mechanisms:**

| mechanism | the filter | example |
|---|---|---|
| `seat_limited` | fixed places; competition is applicants per seat | UPSC 1,096:1 · JEE Main 23.5:1 · NEET 18.7:1 |
| `attrition_limited` | no quota; the filter is the pass mark | GATE 18.7% · CSIR-NET 14.4% · CA Foundation 20.1% |
| `distributed` | one test feeding many independent admissions; **a national ratio would be a fiction** | CUET — 10.7 lakh candidates, no national seat pool |

**Per gate, mandatory:** applicants and seats *or* a pass rate · preparation years · whether
preparation is full time · **cost on every private gate** · `if_unsuccessful` with a populated
`transfers_to`.

**Two rules the validators enforce, both learned the hard way:**

1. **Never claim preparation was worth nothing.** `if_unsuccessful` splits `credential_gained`
   (often null — the real loss) from `transfers_to` and `non_credential_gain` (usually
   substantial). A failed UPSC candidate carries their preparation into every other government
   exam, into teaching and journalism. Misleading a family toward despair is as bad as overselling.
2. **Never report odds without cost on a private gate.** It tells a rich student the truth and a
   poor one a lie — and when the private route is the *only* route, the fee **is** the entry barrier.

**Two findings to carry forward:**

- **Private entrances are often not competition gates at all — they are cost gates.** COMEDK began
  2025 counselling with 26,827 engineering seats and filled 9,637 after four rounds: **over 17,000
  vacant.** Check occupancy before presenting any private entrance as competitive.
- **Medicine is the one place money cannot buy the door open.** NEET governs government, private
  *and deemed* colleges alike (`verified_facts.json#neet-ug-eligibility`).

**Deferring a gate is fine; deferring it silently is not.** Add it to `pending_gates` with the
reason. VITEEE, COMEDK and SRMJEEE currently sit there because their costs could not be sourced
and the validator rejects a private gate without one — **that is the rule working, not failing.**
Selection must follow a principle, not whichever numbers happen to be already fetched.

### Step 2 — probe, then build
`python tools/probe.py "<name>" <defining skills>` before every profession. It reads the graveyard
(57 routed, 4 merged) and will tell you if the candidate was already considered and rejected.
Expect **8–20 professions** per sector. A profession costs economics, verification, AI scoring and
review; a job role costs one line.

Every record needs the full schema in §1, including: `self_employment` as an object with a
mandatory `route` unless `rare`; `entry_competition` naming a gate in `entrance_gates.json` or
`null`; `demand_signal` with `declining` justified by a nuance; `ai_exposure.work_composition`
summing to 100; `role_spread` using only `psychometric_factors.json` slugs.

### Step 3 — three iterations, all required

| # | pass | what it catches |
|---|---|---|
| **1** | **Automated.** `export_csv.py` and `audit.py` both **exit 0**. | derived values, enum drift, broken promises, duplicate job roles, spec drift |
| **2** | **Manual, key by key, every profession.** Read each record whole. | the mis-tiered Laboratory Technician, three wrong `years_to_qualify`, invented council names — none of which iteration 1 caught |
| **3** | **Cross-sector coherence.** Compare against all built sectors. | a profession that duplicates one elsewhere · a boundary contradicting §2 · economics not comparable with a sibling sector · an `ai_exposure` band inconsistent with similar work · a `demand_signal` read off an industry statistic (§8.45) |

Record every correction in the sector `changelog`, and in `DECISIONS.md` §10 if it changed a rule.

### Step 4 — before moving on
Update the status tables in `.claude/CLAUDE.md` and `README.md`. Do not add a `LOCKED` marker —
there is none, deliberately. Finished means both tools clean and every key reviewed twice;
**finished does not mean frozen.**

---

## Final step — independent review

**After all eleven sectors are built and all three iterations have passed**, launch a reviewer
subagent (in .claude/agents folder) with fresh eyes. It must not have built the data.

Brief it to:
1. Read `DECISIONS.md`, then the eleven new sector files.
2. **Find what is missing** — professions an Indian student would expect and cannot find; base
   layers still absent; sectors that are suspiciously small. Basically Revisit the overall  judgment by the main agent, while populating the fields of the profession under check. 
3. **Challenge boundaries** — every profession where the substitution test (§8.95) could plausibly
   go the other way.
4. **Attack the numbers** — every `economics` block marked `verified`; every source that does not
   actually contain a rupee figure; every `demand_signal` inferred from industry size.
5. **Check the audience** — which sectors are closed to a commerce or arts student, and whether
   that is a real property of the work or an artefact of how it was built.
6. **Report only what it can evidence**, ranked by consequence, distinguishing *wrong* from
   *contestable*. It must not edit anything.

---

## Definition of done

- 18 sectors built; `export_csv.py` and `audit.py` both **exit 0**
- **0 broken promises**; 0 duplicate job roles; spec drift clean
- every Tier A profession verified and naming a real, checked licensing body
- every unsourced money figure marked `judgment` and carried in an `admin_review`
- every base-layer gap either filled or explicitly flagged with a reason
- every exam a profession names either present in `entrance_gates.json` or listed in `pending_gates`
  with a reason; alternative_gates never without a primary_gate; every private gate states its cost
- the reviewer's report delivered, with each finding accepted or rebutted in writing
- **no existing rule or built sector amended without having asked first**
