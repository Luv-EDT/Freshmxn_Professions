"""Export profession JSON to per-sector CSV for spreadsheet review.

    python tools/export_csv.py          # every sector file present
    python tools/export_csv.py 01 03    # only those sector numbers

JSON under data/professions/ is the source of truth; build/*.csv is generated.

Also validates:
  - industrial_sectors tags exist in the master list
  - degree_dependency / mid_stream_entry values are legal
  - class12_prerequisite is "any" or a list of known subjects
  - verification block is present and internally consistent
  - profession_count matches reality
"""

import csv
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "professions"
OUT = ROOT / "build"

COLUMNS = [
    "professional_sector",
    "id",
    "profession",
    "one_liner",
    "job_roles",
    "industrial_sectors",
    "degree_dependency",
    "mid_stream_entry",
    "class12_prerequisite",
    "entrance_exams",
    "entry_gate",
    "applicants_per_seat",
    "prep_years",
    "licensing_body",
    "after_undergrad",
    "self_employment",
    "self_emp_ceiling_lpa",
    "self_emp_route",
    "india_demand",
    "pathway",
    "ai_exposure",
    "ai_reason",
    "role_spread",
    "years_to_qualify",
    "cost_of_entry_lakh",
    "early_earnings_lpa",
    "mid_career_lpa",
    "payback_years",
    "ship",
    "failed_rules",
    "path_to_entry",
    "entry_window",
    "verified",
    "source",
    "admin_review",
    "review_priority",
    "review_reason",
    "nuances",
]

DEGREE_VALUES = {"none", "certificate", "undergrad", "professional"}
ENTRY_VALUES = {"open", "after_any_degree", "restart_undergrad"}
AFTER_UG = {"masters_required", "masters_is_the_entry", "masters_advantage", "work_first"}
# self_employment is an OBJECT, not a string. The ceiling lives with the thing it belongs to.
# Reason it exists: mid_career_lpa is EMPLOYED-ONLY by design (§8.4), which deleted exactly the
# half of the income where the trades win and made a mason look trapped at 3.0 LPA for life.
SELF_EMP = {"common", "possible_later", "rare"}
BANDS = {"low", "medium", "high"}
PROTECTIONS = {"legal_accountability", "physical_unstructured", "human_trust_is_the_product", "irreversible_risk"}
EXPOSURES = {"output_is_digital", "routine_rule_based", "no_client_relationship", "entry_level_heavy"}
SUBJECTS = {"physics", "chemistry", "maths", "biology", "english", "accountancy", "economics"}
TIERS = {"A", "B", "C"}
STATUSES = {"verified", "judgment"}
# economics.distribution — what SHAPE the money is, which decides whether a midpoint means
# anything at all. "range" is the ordinary case and the default.
#   power_law   a few earn enormously, most earn little, and there is almost no middle. A
#               midpoint describes nobody, so the compensation filter MUST NOT fire on it.
#   bimodal     two distinct populations, not a spread — a KVS teacher at 8.3 lakh and a private
#               school teacher at 1.5; a government MBBS seat at 1-5 lakh and a private one at 60+.
#               The midpoint is real arithmetic and describes almost nobody.
DISTRIBUTIONS = {"range", "power_law", "bimodal"}

# DEMAND is the answer to "should this be dropped?" — and the answer is almost always no.
#   high       hiring at volume today
#   moderate   steady, unremarkable hiring
#   low        thin market, few posts — but STABLE. Physicist and Mathematician live here.
#   declining  total employment is structurally SHRINKING because technology is absorbing
#              the work itself. Still listed, because the work exists and pays today.
# There is no 'obsolete' value: work that has actually died — typewriter mechanic, stone
# tool maker — is never entered in the first place. See DECISIONS.md §8.45.
DEMAND = {"high", "moderate", "low", "declining"}
PATHWAY = {"india", "abroad", "any"}

# entry_window keys, pinned. DECISIONS.md §4.3 documented `constrained_routes[]` and
# `open_routes[]` while every record used `constrained_route` and `bypass` as strings, and
# spec_drift() never noticed because it only compares TOP-LEVEL profession keys. Nested shapes
# need pinning too.
ENTRY_WINDOW_KEYS = {"max_years_since_class12", "max_age", "is_hard_block",
                     "constrained_route", "bypass"}


def gates():
    return json.loads((ROOT / "data" / "entrance_gates.json").read_text(encoding="utf-8"))["gates"]


GATES = gates()


def filter_rules():
    return json.loads((ROOT / "data" / "filter_rules.json").read_text(encoding="utf-8"))["compensation_filter"]


RULES = filter_rules()


def ships(p):
    """Evaluate the compensation filter. DERIVED — never stored on the record.

    Returns (ship: bool, failed: list[str]). The application does exactly this at query time.
    """
    ec = p.get("economics") or {}
    mid = ec.get("mid_career_midpoint")
    if mid is None:
        return True, []
    # A power-law record's midpoint is arithmetic over a distribution with no middle. Filtering on
    # it would delete a profession on the strength of a number the record itself calls meaningless.
    if ec.get("distribution") == "power_law":
        return True, []
    # Same principle, second case: mid_career EXCLUDES business ownership by design (see
    # filter_rules.json → known_limitations). Where going independent is NORMAL and the record
    # openly owes an owner-income figure it could not source, the midpoint is a floor someone
    # leaves, not a ceiling they hit. Automobile Mechanic is the proof — cut at 4.25 while its own
    # SOURCED self_employment ceiling is 6–18 lakh. Both conditions are required: 'common' alone
    # would spare records whose number is simply low, and admin_review alone spares employees.
    # It exempts the PAY FLOOR ONLY, never the AI clause. Ownership answers "is this figure the
    # whole income"; it does not answer "is this work disappearing". Website & Online Store Builder
    # is self-employed AND owes an owner figure AND scores 72 — the clause was written for exactly
    # that record, and letting ownership override it would have quietly cancelled the clause.
    se = p.get("self_employment") or {}
    owner_exempt = (se.get("likelihood") == "common"
                    and (p.get("admin_review") or {}).get("required"))
    failed = []
    if mid < RULES["mid_career_floor_lpa"] and not owner_exempt:
        failed.append(f"mid_career {mid} < floor {RULES['mid_career_floor_lpa']}")
    clause = RULES["ai_penalty_clause"]
    if mid < clause["mid_career_below_lpa"] and p["ai_exposure"]["band"] == clause["when_ai_exposure"]:
        failed.append(f"mid_career {mid} < {clause['mid_career_below_lpa']} with ai_exposure high")
    return not failed, failed


def check_economics(pid, p, out):
    """Only the STORED numbers are validated. ship is derived, so there is nothing to drift."""
    e = p.get("economics")
    if not e:
        out.append(f"{pid}: missing economics block")
        return
    if e.get("distribution", "range") not in DISTRIBUTIONS:
        out.append(f"{pid}: bad economics.distribution '{e.get('distribution')}' — "
                   f"one of {sorted(DISTRIBUTIONS)}")
    lo, hi = (e.get("mid_career_lpa") or "0-0").split("-")
    mid = e.get("mid_career_midpoint")
    if mid is None or abs(mid - (float(lo) + float(hi)) / 2) > 1e-9:
        out.append(f"{pid}: mid_career_midpoint does not match mid_career_lpa range")
    cost, early = e.get("cost_of_entry_lakh"), (e.get("early_earnings_lpa") or "0-0").split("-")
    if cost is not None:
        expect = round(cost / ((float(early[0]) + float(early[1])) / 2), 2)
        if abs(e.get("payback_years", -1) - expect) > 0.01:
            out.append(f"{pid}: payback_years says {e.get('payback_years')}, cost/early gives {expect}")


def known_tags():
    master = json.loads((ROOT / "data" / "industrial_sectors.json").read_text(encoding="utf-8"))
    return {s["code"] for s in master["nsdc_sector_skill_councils"]} | {
        s["code"] for s in master["extension_tags"]
    }


def check(p, valid_tags):
    """Return a list of problems with one profession record."""
    out = []
    pid = p.get("id", "<no id>")

    unknown = [t for t in p["industrial_sectors"] if t not in valid_tags]
    if unknown:
        out.append(f"{pid}: unknown industrial tag(s) {unknown}")
    if p["degree_dependency"] not in DEGREE_VALUES:
        out.append(f"{pid}: bad degree_dependency '{p['degree_dependency']}'")
    if p["mid_stream_entry"] not in ENTRY_VALUES:
        out.append(f"{pid}: bad mid_stream_entry '{p['mid_stream_entry']}'")

    prereq = p["class12_prerequisite"]
    if prereq != "any":
        if not isinstance(prereq, list):
            out.append(f"{pid}: class12_prerequisite must be 'any' or a list of subjects")
        else:
            bad = [s for s in prereq if s not in SUBJECTS]
            if bad:
                out.append(f"{pid}: unknown class 12 subject(s) {bad}")

    v = p.get("verification")
    if not v:
        out.append(f"{pid}: missing verification block")
    else:
        if v.get("tier") not in TIERS:
            out.append(f"{pid}: bad verification tier '{v.get('tier')}'")
        if v.get("status") not in STATUSES:
            out.append(f"{pid}: bad verification status '{v.get('status')}'")
        if v.get("status") == "verified" and not v.get("source"):
            out.append(f"{pid}: claims verified but has no source")
        if v.get("tier") == "A" and v.get("status") != "verified":
            out.append(f"{pid}: Tier A (regulated) must be verified, not judgment")
        if v.get("tier") == "A" and not p.get("licensing_body"):
            out.append(f"{pid}: Tier A must name a licensing_body")

    if p.get("after_undergrad") not in AFTER_UG:
        out.append(f"{pid}: bad after_undergrad '{p.get('after_undergrad')}'")
    se = p.get("self_employment")
    if not isinstance(se, dict):
        out.append(f"{pid}: self_employment must be an object, not '{se}'")
    else:
        if se.get("likelihood") not in SELF_EMP:
            out.append(f"{pid}: bad self_employment.likelihood '{se.get('likelihood')}'")
        if se.get("likelihood") == "rare":
            if se.get("ceiling_lpa") or se.get("route"):
                out.append(f"{pid}: self_employment 'rare' must have null ceiling_lpa and route")
        else:
            if not (se.get("route") or "").strip():
                out.append(f"{pid}: self_employment '{se.get('likelihood')}' needs a route — "
                           f"how does someone actually get there?")

    win = p.get("entry_window")
    if win:
        unknown = set(win) - ENTRY_WINDOW_KEYS
        if unknown:
            out.append(f"{pid}: entry_window has unknown key(s) {sorted(unknown)} — "
                       f"the documented shape is {sorted(ENTRY_WINDOW_KEYS)}")

    comp = p.get("entry_competition")
    if comp is not None:
        if comp.get("primary_gate") and comp["primary_gate"] not in GATES:
            out.append(f"{pid}: entry_competition.primary_gate '{comp['primary_gate']}' "
                       f"is not in entrance_gates.json")
        for g in comp.get("alternative_gates") or []:
            if g not in GATES:
                out.append(f"{pid}: entry_competition alternative gate '{g}' is not in entrance_gates.json")
        if not comp.get("primary_gate") and not comp.get("alternative_gates"):
            out.append(f"{pid}: entry_competition present but names no gate — use null instead")

    ds = p.get("demand_signal") or {}
    if ds.get("india_demand") not in DEMAND:
        out.append(f"{pid}: bad india_demand '{ds.get('india_demand')}' — one of {sorted(DEMAND)}")
    if ds.get("pathway") not in PATHWAY:
        out.append(f"{pid}: bad pathway '{ds.get('pathway')}' — one of {sorted(PATHWAY)}")
    if ds.get("india_demand") == "declining" and not any(
            n.get("field") == "demand_signal" for n in p.get("nuances", [])):
        # 'declining' is a claim that a profession is shrinking. Never assert that bare.
        out.append(f"{pid}: india_demand 'declining' needs a nuance on demand_signal saying WHY")

    r = p.get("admin_review")
    ai = p.get("ai_exposure")
    if not ai:
        out.append(f"{pid}: missing ai_exposure block")
    else:
        w = ai.get("work_composition") or {}
        keys = ("knowledge_foundational", "knowledge_retrievable", "skill_physical", "skill_digital", "clarity")
        vals = [w.get(k) for k in keys]
        if None in vals:
            out.append(f"{pid}: work_composition needs all of {keys}")
        elif sum(vals) != 100:
            out.append(f"{pid}: work_composition sums to {sum(vals)}, must be 100")
        else:
            raw = w["knowledge_retrievable"] + w["skill_digital"]
            if ai.get("exposure_raw") != raw:
                out.append(f"{pid}: exposure_raw says {ai.get('exposure_raw')}, model gives {raw}")
            band = "high" if raw >= 65 else ("medium" if raw >= 40 else "low")
            if ai.get("legal_accountability"):
                band = {"high": "medium", "medium": "low", "low": "low"}[band]
            if ai.get("band") != band:
                out.append(f"{pid}: ai_exposure band says '{ai.get('band')}', raw {raw} gives '{band}'")
        if ai.get("band") not in BANDS:
            out.append(f"{pid}: bad ai_exposure band")
        if not ai.get("reason"):
            out.append(f"{pid}: ai_exposure needs a reason naming exposed vs safe job roles")
        # A high band no longer forces an admin_review. ai_exposure SPEAKS FOR ITSELF — the
        # application reads the tag and frames the warning, and no human decision is owed in the
        # data. The same rule was removed from audit.py when that was decided; it survived here
        # for three sectors, failing on exit code while the printed output read clean.

    if not r:
        out.append(f"{pid}: missing admin_review block")
    elif r.get("required") and not r.get("reason"):
        out.append(f"{pid}: admin_review required but no reason given")

    check_economics(pid, p, out)

    w = p.get("entry_window")
    if w:
        if w.get("is_hard_block") is None:
            out.append(f"{pid}: entry_window must state is_hard_block")
        elif w.get("is_hard_block") is False and not w.get("bypass"):
            out.append(f"{pid}: entry_window says not a hard block but lists no bypass")
        elif w.get("is_hard_block") is True and w.get("bypass"):
            out.append(f"{pid}: entry_window claims hard block but an open route exists")

    return out


def export(path, valid_tags):
    data = json.loads(path.read_text(encoding="utf-8"))
    sector = data["professional_sector"]
    problems = []

    OUT.mkdir(exist_ok=True)
    target = OUT / f"{path.stem}.csv"
    with target.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for p in data["professions"]:
            problems += check(p, valid_tags)
            prereq = p["class12_prerequisite"]
            v = p.get("verification", {})
            r = p.get("admin_review", {})
            w = p.get("entry_window")
            writer.writerow(
                {
                    "professional_sector": sector,
                    "id": p["id"],
                    "profession": p["profession"],
                    "one_liner": p.get("one_liner", ""),
                    "job_roles": " | ".join(p["job_roles"]),
                    "industrial_sectors": " | ".join(p["industrial_sectors"]),
                    "degree_dependency": p["degree_dependency"],
                    "mid_stream_entry": p["mid_stream_entry"],
                    "class12_prerequisite": prereq if prereq == "any" else " + ".join(prereq),
                    "entry_gate": ((p.get("entry_competition") or {}).get("primary_gate") or ""),
                    "applicants_per_seat": (
                        GATES.get(((p.get("entry_competition") or {}).get("primary_gate") or ""), {})
                        .get("applicants_per_seat") or ""),
                    "prep_years": (
                        GATES.get(((p.get("entry_competition") or {}).get("primary_gate") or ""), {})
                        .get("preparation_years") or ""),
                    "entrance_exams": " | ".join(
                        p.get("entrance_exams", {}).get("public_routes", [])
                        + p.get("entrance_exams", {}).get("private_entrances", [])
                    ) or "none",
                    "licensing_body": p.get("licensing_body") or "",
                    "after_undergrad": p.get("after_undergrad", ""),
                    "self_employment": (p.get("self_employment") or {}).get("likelihood", ""),
                    "self_emp_ceiling_lpa": (p.get("self_employment") or {}).get("ceiling_lpa") or "",
                    "self_emp_route": (p.get("self_employment") or {}).get("route") or "",
                    "india_demand": (p.get("demand_signal") or {}).get("india_demand", ""),
                    "pathway": (p.get("demand_signal") or {}).get("pathway", ""),
                    "ai_exposure": (p.get("ai_exposure") or {}).get("band", ""),
                    "ai_reason": (p.get("ai_exposure") or {}).get("reason", ""),
                    "role_spread": " || ".join(
                        f"[{', '.join(g['roles'])}] higher: {', '.join(g['higher']) or '-'}"
                        f" / lower: {', '.join(g['lower']) or '-'}"
                        for g in (p.get("role_spread") or {}).get("deviating_roles", [])),
                    "years_to_qualify": p.get("years_to_qualify", ""),
                    "cost_of_entry_lakh": (p.get("economics") or {}).get("cost_of_entry_lakh", ""),
                    "early_earnings_lpa": (p.get("economics") or {}).get("early_earnings_lpa", ""),
                    "mid_career_lpa": (p.get("economics") or {}).get("mid_career_lpa", ""),
                    "payback_years": (p.get("economics") or {}).get("payback_years", ""),
                    "ship": "yes" if ships(p)[0] else "NO",
                    "failed_rules": " ; ".join(ships(p)[1]),
                    "path_to_entry": " -> ".join(
                        f"{s['stage']}: {s['requirement']}" for s in p.get("path_to_entry", [])
                    ),
                    "entry_window": (
                        ""
                        if not w
                        else ("HARD BLOCK: " if w.get("is_hard_block") else "route limit: ")
                        + str(w.get("constrained_route", ""))
                        + (" | bypass: " + "; ".join(w.get("bypass", [])) if w.get("bypass") else "")
                    ),
                    "verified": v.get("status", ""),
                    "source": v.get("source") or "",
                    "admin_review": "REVIEW" if r.get("required") else "",
                    "review_priority": r.get("priority") or "",
                    "review_reason": r.get("reason") or "",
                    "nuances": " || ".join(
                        f"[{n['field']}] {n['statement']}" for n in p.get("nuances", [])),
                }
            )

    count = len(data["professions"])
    declared = data.get("profession_count")
    if declared is not None and declared != count:
        problems.append(f"profession_count says {declared}, file has {count}")

    filtered = [p for p in data["professions"] if not ships(p)[0]]
    verified = sum(
        1 for p in data["professions"] if p.get("verification", {}).get("status") == "verified"
    )
    print(f"{target.relative_to(ROOT)}  ({count} professions, {verified} verified, {count - verified} judgment)")
    for issue in problems:
        print(f"  ! {issue}")

    if filtered:
        print(f"  filtered by compensation rule ({len(filtered)} of {count}, derived not stored):")
        for p in filtered:
            print(f"    x {p['profession']:42} {' ; '.join(ships(p)[1])}")
    order = {"high": 0, "medium": 1, "low": 2}
    queue = sorted(
        (p for p in data["professions"] if p.get("admin_review", {}).get("required")),
        key=lambda p: order.get(p["admin_review"].get("priority"), 9),
    )
    if queue:
        print(f"\n  ADMIN REVIEW QUEUE ({len(queue)} of {count}):")
        for p in queue:
            print(f"    [{p['admin_review']['priority']:6}] {p['profession']}")
            print(f"             {p['admin_review']['reason']}")
    return len(problems)


def combine(files):
    """Also emit build/ALL-professions.csv — every sector in one sheet.

    The per-sector files stay, because a sector is the unit a human reviews. This is for the
    check they cannot do: comparing ACROSS sectors. That pass caught three real defects in the
    18-sector build and every one of them was invisible inside a single file — Sector 8 pricing
    designers above Sector 1's software developers, Sector 15 pricing agricultural engineers above
    Sector 2's mechanical ones, and Sector 16 putting a deck officer five lakh above the marine
    engineer holding the parallel certificate on the same ship.

    A number can be individually valid and collectively false, and you cannot see that with
    eighteen files open. `professional_sector` is already the first column, so it sorts.

    Only written when exporting the whole dataset — a partial run would produce a misleading
    "ALL" sheet containing two sectors.
    """
    if len(files) < len(list(SRC.glob("*.json"))):
        return
    target = OUT / "ALL-professions.csv"
    rows = []
    for f in files:
        csv_path = OUT / f"{f.stem}.csv"
        if not csv_path.exists():
            continue
        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            rows += list(csv.DictReader(fh))
    with target.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{target.as_posix()}  ({len(rows)} professions, all sectors, for cross-sector sorting)")

    combine_json(files)


def combine_json(files):
    """build/ALL-professions.json — every sector in one file, LOSSLESS.

    The CSV flattens: nuances collapse to one pipe-joined cell, work_composition becomes four
    columns, entry_window and entry_competition become two. That is right for a spreadsheet and
    wrong for anything that consumes the data — a psychometric pipeline keyed on profession.id
    needs the nested objects back, and reconstructing them from CSV is guesswork.

    So this is the CSV's opposite number: no flattening, no dropped keys, every record exactly as
    it sits in its sector file, with the two sector fields folded in so a record still knows where
    it came from once the eighteen files are gone.

    GENERATED on every full run, never hand-edited — same rule as the CSVs. A hand-maintained
    second sheet was tried and removed: it went stale within an hour, still naming the Bar Council
    of India as the Judicial Services Officer's licensing body after that was corrected everywhere
    else. Two views of one dataset means one of them is always wrong.
    """
    payload = {
        "generated_on": datetime.date.today().isoformat(),
        "generated_by": "tools/export_csv.py — do not hand-edit; edit data/professions/*.json",
        "spec": "DECISIONS.md",
        "note": "Lossless union of the 18 sector files. Every profession carries every field, "
                "nested structures intact. `filter` and `ship` are DERIVED from "
                "data/filter_rules.json and recomputed on every run — read the rule there rather "
                "than trusting the flag. Shared registries are NOT inlined: entrance_exams and "
                "entry_competition reference data/entrance_gates.json, and verification.source "
                "references data/verified_facts.json, both by key.",
        "counts": {},
        "sectors": [],
        "professions": [],
    }
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        payload["sectors"].append({
            "professional_sector_id": d["professional_sector_id"],
            "professional_sector": d["professional_sector"],
            "version": d["version"],
            "profession_count": d["profession_count"],
            "source_file": f"data/professions/{f.name}",
            "sector_verification_note": d.get("sector_verification_note"),
        })
        for p in d["professions"]:
            payload["professions"].append({
                "professional_sector_id": d["professional_sector_id"],
                "professional_sector": d["professional_sector"],
                **p,
            })
    ps = payload["professions"]
    payload["counts"] = {
        "sectors": len(payload["sectors"]),
        "professions": len(ps),
        "job_roles": sum(len(p["job_roles"]) for p in ps),
        "nuances": sum(len(p["nuances"]) for p in ps),
        "ships": sum(1 for p in ps if p["filter"]),
        "fails_compensation_filter": sum(1 for p in ps if not p["filter"]),
        "admin_review_required": sum(1 for p in ps if p["admin_review"]["required"]),
    }
    target = OUT / "ALL-professions.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    kb = target.stat().st_size // 1024
    print(f"{target.as_posix()}  ({len(ps)} professions, nested structures intact, {kb} KB)")


def main():
    wanted = sys.argv[1:]
    files = sorted(SRC.glob("*.json"))
    if wanted:
        files = [f for f in files if any(f.name.startswith(w) for w in wanted)]
    if not files:
        print("no matching sector files in data/professions/")
        return 1

    valid_tags = known_tags()
    issues = sum(export(f, valid_tags) for f in files)
    combine(files)
    if issues:
        print(f"\n{issues} issue(s) found.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
