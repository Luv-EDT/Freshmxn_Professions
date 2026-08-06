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
    "licensing_body",
    "after_undergrad",
    "self_employment",
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
SELF_EMP = {"common", "possible_later", "rare"}
BANDS = {"low", "medium", "high"}
PROTECTIONS = {"legal_accountability", "physical_unstructured", "human_trust_is_the_product", "irreversible_risk"}
EXPOSURES = {"output_is_digital", "routine_rule_based", "no_client_relationship", "entry_level_heavy"}
SUBJECTS = {"physics", "chemistry", "maths", "biology", "english", "accountancy", "economics"}
TIERS = {"A", "B", "C"}
STATUSES = {"verified", "judgment"}


def filter_rules():
    return json.loads((ROOT / "data" / "filter_rules.json").read_text(encoding="utf-8"))["compensation_filter"]


RULES = filter_rules()


def ships(p):
    """Evaluate the compensation filter. DERIVED — never stored on the record.

    Returns (ship: bool, failed: list[str]). The application does exactly this at query time.
    """
    mid = (p.get("economics") or {}).get("mid_career_midpoint")
    if mid is None:
        return True, []
    failed = []
    if mid < RULES["mid_career_floor_lpa"]:
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
    if p.get("self_employment") not in SELF_EMP:
        out.append(f"{pid}: bad self_employment '{p.get('self_employment')}'")

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
        if ai.get("band") == "high" and not (r or {}).get("required"):
            out.append(f"{pid}: ai_exposure high must be flagged for admin_review")

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
                    "entrance_exams": " | ".join(
                        p.get("entrance_exams", {}).get("national", [])
                        + p.get("entrance_exams", {}).get("private_reputed", [])
                    ) or "none",
                    "licensing_body": p.get("licensing_body") or "",
                    "after_undergrad": p.get("after_undergrad", ""),
                    "self_employment": p.get("self_employment", ""),
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
    if issues:
        print(f"\n{issues} issue(s) found.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
