"""Is a candidate profession already covered as a job role somewhere?

Before adding anything, check. New professions are expensive — they need economics,
verification, AI scoring and review. A job role costs one line.

    python tools/probe.py "Semiconductor Fab Technician" cleanroom wafer fab semiconductor

First argument is the candidate name; the rest are the skills or terms that define it.
Reports every existing profession or job role that overlaps, so the call is made on
evidence rather than instinct.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP = {"engineer", "technician", "scientist", "analyst", "developer", "officer",
        "operator", "specialist", "manager", "designer", "researcher", "and", "the"}


def load():
    out = []
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            out.append((d["professional_sector"], p))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    name = sys.argv[1]
    terms = [t.lower() for t in (sys.argv[2:] or name.split())]
    terms = [t for t in terms if t not in STOP]

    print(f"CANDIDATE: {name}")
    print(f"terms: {', '.join(terms)}\n")

    hits = []
    for sector, p in load():
        matched_roles = [r for r in p["job_roles"] if any(t in r.lower() for t in terms)]
        prof_match = [t for t in terms if t in p["profession"].lower()]
        line_match = [t for t in terms if t in p["one_liner"].lower()]
        score = len(matched_roles) * 3 + len(prof_match) * 4 + len(line_match)
        if score:
            hits.append((score, sector, p, matched_roles, prof_match, line_match))

    if not hits:
        print("  NO OVERLAP FOUND — a genuinely new profession, or the terms are wrong.")
        print("  Try again with the skills that define the work, not the job title.")
        return 0

    for score, sector, p, roles, pm, lm in sorted(hits, reverse=True, key=lambda x: x[0]):
        print(f"  [{score:>2}] {p['profession']}  ({sector})")
        print(f"       degree={p['degree_dependency']}  tags={','.join(p['industrial_sectors'][:4])}")
        if pm:
            print(f"       name matches: {', '.join(pm)}")
        if roles:
            print(f"       job roles: {' | '.join(roles)}")
        if lm:
            print(f"       one_liner mentions: {', '.join(lm)}")
        print()

    print("  VERDICT GUIDE")
    print("    strong overlap  -> add as a job_role on the closest profession")
    print("    partial overlap -> ask whether the SKILL SET differs, not the industry")
    print("    no overlap      -> justifies a new profession")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
