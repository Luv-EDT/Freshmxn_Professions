"""Render a preference preset as a three-tier view: SECTOR > PROFESSION > JOB ROLES.

    python tools/track_view.py                 # core_engineering (the only track so far)
    python tools/track_view.py --list          # what presets exist

Writes build/<track>-track.json.

WHY THIS IS GENERATED AND NOT A SECOND SOURCE OF TRUTH: a student who wants only core engineering
needs a smaller list, and the obvious thing to do is write one. This repo has already paid for
that mistake — the hand-maintained COMPACT sheet went stale within an hour and was still naming
the Bar Council of India as the Judicial Services Officer's licensing body after the correction had
landed everywhere else. DECISIONS.md §8.7b settles the principle for exactly this case:
**aspiration is served by a QUERY, never by a column.** So membership is computed from the data on
every run, and a profession that changes cannot fall out of date here.

MEMBERSHIP has two parts, both declared in data/filter_rules.json → preference_filters:

  1. `engineering_gated`, a RULE — sector 2, or a PCM class-12 gate, or an ENGINEERING route in
     path_to_entry (B.Tech, B.E., polytechnic, or an ITI in an engineering trade).
  2. `also_include`, a NAMED LIST WITH REASONS — Patent Agent, the supply-chain and management
     professions, the ITI instructor and engineering faculty. Six of the eight fail the rule and
     belong anyway. The same visible-exception pattern as sweep.py's EXEMPT dict: a judgment call
     written down can be argued with; one buried in a regex cannot.

EVERY MEMBER CARRIES `in_track_because`, naming the clause or the reason that admitted it. A view
whose membership cannot be interrogated is a hand-list with extra steps.

INDUSTRY DOMAINS are expanded from each record's `industrial_sectors` codes to full council names
via data/industrial_sectors.json, because "CGSC" tells a 15-year-old nothing and "Capital Goods
Skill Council" tells them where the jobs are.
"""

import argparse
import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build"

# WHAT IS NOT A MEMBERSHIP TEST, AND WHY.
#
# The first version of this rule admitted any profession carrying two or more manufacturing-side
# skill councils. It let in Firefighter, Cybersecurity Specialist, Laboratory Technician and Game
# & Interactive Media Developer — because a fire officer works at a refinery and a security
# specialist has manufacturing clients. That is the cross-cutting rule in DECISIONS.md §2.2 being
# broken by its own author: an industrial tag names an EMPLOYER, and "engineers hire this person"
# is not "this person does engineering". The clause was removed rather than patched.
#
# Bare "ITI" and bare "diploma" went the same way. They matched Tailor & Garment Maker (ITI in
# sewing) and Production Crew & Studio Technician. The route has to be an ENGINEERING route.
ROUTE_RE = re.compile(
    r"B\.?\s?Tech|B\.?E\.\b|polytechnic|diploma in [a-z& ]*engineering|"
    r"ITI (?:in |trade)[a-z& ]*(?:fitter|turner|electric|mechanic|weld|machinist|draught|"
    r"instrument|refrigerat|plumb|carpent|electron)",
    re.I)


def councils():
    d = json.loads((ROOT / "data" / "industrial_sectors.json").read_text(encoding="utf-8"))
    out = {}
    for x in d["nsdc_sector_skill_councils"] + d["extension_tags"]:
        out[x["code"]] = x["name"]
    return out


def professions():
    out = []
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            out.append((d["professional_sector_id"], d["professional_sector"], p))
    return out


def engineering_gated(sid, p):
    """The rule half of membership. Returns the reason it matched, or None."""
    if sid == 2:
        return "Sector 2 — Engineering & Making"
    pre = p["class12_prerequisite"]
    if pre != "any" and "physics" in pre and "maths" in pre:
        return "class 12 Physics + Maths gate"
    if ROUTE_RE.search(json.dumps(p.get("path_to_entry", ""))):
        return "engineering route in path_to_entry (B.Tech / B.E. / polytechnic / engineering ITI)"
    return None


def entry_level(p):
    """Which ladder does a student climb to reach this?

    Three rungs, decided by degree_dependency and what path_to_entry actually mentions. The
    distinction that matters to a 15-year-old is not the sector but WHAT THEY HAVE TO GET FIRST.
    """
    dd = p["degree_dependency"]
    if dd in ("undergrad", "professional"):
        return "degree"
    path = json.dumps(p.get("path_to_entry", ""))
    if re.search(r"diploma|polytechnic", path, re.I):
        return "diploma"
    return "trade_certificate"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", default="core_engineering_track")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    rules = json.loads((ROOT / "data" / "filter_rules.json").read_text(encoding="utf-8"))
    presets = rules["preference_filters"]["presets"]
    if args.list:
        for k, v in presets.items():
            print(f"  {k}\n      {v.get('intent', '')[:150]}")
        return 0
    if args.track not in presets:
        print(f"! no preset '{args.track}'. Try --list")
        return 1
    preset = presets[args.track]
    also = preset.get("also_include", {})

    name = councils()
    levels = {"degree": {}, "diploma": {}, "trade_certificate": {}}
    kept, reasons = 0, {}
    for sid, sname, p in professions():
        why = engineering_gated(sid, p)
        if why is None and p["profession"] in also:
            why = f"named inclusion — {also[p['profession']]}"
        if why is None:
            continue
        kept += 1
        reasons[p["profession"]] = why
        # THE WHOLE RECORD, plus two additions. An earlier version copied nineteen chosen fields
        # and silently dropped nuances, path_to_entry, verification and admin_review — which is
        # the COMPACT-sheet failure again in a new costume: a partial copy is a second dataset,
        # and a second dataset is one that will eventually disagree with the first. A LOSSLESS
        # view cannot diverge, because there is nothing in it that is not in the source.
        entry = dict(p)
        entry["professional_sector"] = sname
        entry["professional_sector_id"] = sid
        entry["in_track_because"] = why
        # `industrial_sectors` stays untouched; this is the same list with the codes spelled out,
        # because "CGSC" tells a 15-year-old nothing and "Capital Goods Skill Council" tells them
        # where the jobs are.
        entry["industry_domains"] = [{"code": c, "name": name.get(c, c)}
                                     for c in p["industrial_sectors"]]
        levels[entry_level(p)].setdefault((sid, sname), []).append(entry)

    payload = {
        "track": args.track,
        "generated_on": datetime.date.today().isoformat(),
        "generated_by": "tools/track_view.py — GENERATED VIEW, do not hand-edit. Membership is "
                        "recomputed from data/professions/*.json on every run.",
        "source_of_truth": "data/professions/*.json — this file is a query result, not a dataset",
        "intent": preset.get("intent"),
        "rule": preset.get("rule"),
        "named_inclusions": also,
        "THE COST — SHOW THIS TO THE STUDENT": preset.get("THE COST - SHOW THIS TO THE STUDENT"),
        "tiers": "professional_sector > profession > job_roles, with industry_domains expanded "
                 "from each record's industrial_sectors codes",
        "counts": {},
        "entry_levels": {},
    }
    total_roles = 0
    for lvl, bysector in levels.items():
        payload["entry_levels"][lvl] = [
            {"professional_sector_id": sid, "professional_sector": sname,
             "professions": sorted(ps, key=lambda x: x["profession"])}
            for (sid, sname), ps in sorted(bysector.items())]
        total_roles += sum(len(p["job_roles"]) for ps in bysector.values() for p in ps)
    payload["counts"] = {
        "professions_in_track": kept,
        "of_total": len(professions()),
        "job_roles": total_roles,
        "sectors_touched": len({s for lv in levels.values() for s in lv}),
        "by_entry_level": {k: sum(len(v) for v in lv.values()) for k, lv in levels.items()},
    }

    OUT.mkdir(exist_ok=True)
    target = OUT / f"{args.track.replace('_track', '').replace('_', '-')}-track.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    c = payload["counts"]
    print(f"{target.relative_to(ROOT).as_posix()}")
    print(f"  {c['professions_in_track']} of {c['of_total']} professions, {c['job_roles']} job "
          f"roles, {c['sectors_touched']} sectors")
    for lvl, n in c["by_entry_level"].items():
        print(f"    {lvl:<18} {n}")
    for lvl, bysector in sorted(payload["entry_levels"].items()):
        print(f"\n  {lvl.upper()}")
        for s in bysector:
            names = ", ".join(p["profession"] for p in s["professions"])
            print(f"    S{s['professional_sector_id']:<3} {names[:96]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
