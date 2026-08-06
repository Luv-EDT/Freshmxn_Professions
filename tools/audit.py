"""Second-pass audit. Cross-field consistency the per-field validator cannot see.

export_csv.py checks each field is legal on its own. This checks whether the fields
AGREE WITH EACH OTHER — which is where real errors hide. Run both before shipping a sector.

    python tools/audit.py            # every sector
    python tools/audit.py 01         # one sector
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "data" / "filter_rules.json").read_text(encoding="utf-8"))["compensation_filter"]
FACTORS = {x["slug"] for g in json.loads(
    (ROOT / "data" / "psychometric_factors.json").read_text(encoding="utf-8"))["groups"] for x in g["factors"]}


def audit(p):
    """Return (errors, warnings) for one profession."""
    e, w = [], []
    pid, ai, ec = p["id"], p["ai_exposure"], p["economics"]
    comp = ai["work_composition"]

    # --- licensing must agree with degree tier and verification ---
    if p["degree_dependency"] == "professional" and not p["licensing_body"]:
        e.append("degree_dependency 'professional' but no licensing_body named")
    if p["licensing_body"] and p["verification"]["tier"] != "A":
        e.append(f"has a licensing_body but verification tier is {p['verification']['tier']}, expected A")
    if p["licensing_body"] and not ai["legal_accountability"]:
        w.append("licensed profession but ai_exposure.legal_accountability is false")
    if ai["legal_accountability"] and not p["licensing_body"]:
        e.append("claims legal_accountability but names no licensing_body")

    # --- subject gates must agree with entrance exams and entry route ---
    gated = p["class12_prerequisite"] != "any"
    exams = p["entrance_exams"]
    has_exam = bool(exams.get("national") or exams.get("private_reputed"))
    if gated and not has_exam:
        w.append("has a class 12 subject gate but lists no entrance exam that enforces it")
    if p["mid_stream_entry"] == "restart_undergrad" and not gated:
        w.append("restart_undergrad but class12_prerequisite is 'any' — why can't they enter mid-stream?")

    # --- entry_window internal logic ---
    win = p.get("entry_window")
    if win:
        if win["is_hard_block"] and win.get("bypass"):
            e.append("entry_window claims hard block but lists a bypass")
        if not win["is_hard_block"] and not win.get("bypass"):
            e.append("entry_window says not a hard block but names no bypass")
        if win.get("max_years_since_class12") is None and win.get("max_age") is None:
            w.append("entry_window present but neither max_years_since_class12 nor max_age is set")

    # --- economics must be internally coherent ---
    e_lo, e_hi = (float(x) for x in ec["early_earnings_lpa"].split("-"))
    m_lo, m_hi = (float(x) for x in ec["mid_career_lpa"].split("-"))
    if m_lo < e_lo:
        e.append(f"mid_career floor {m_lo} below early_earnings floor {e_lo} — career goes backwards")
    if m_hi <= e_hi:
        w.append(f"mid_career ceiling {m_hi} at or below early ceiling {e_hi} — no progression")
    if abs(ec["mid_career_midpoint"] - (m_lo + m_hi) / 2) > 1e-9:
        e.append("mid_career_midpoint does not match its range")
    if abs(ec["payback_years"] - round(ec["cost_of_entry_lakh"] / ((e_lo + e_hi) / 2), 2)) > 0.01:
        e.append("payback_years does not match cost / early_earnings")
    if p["degree_dependency"] == "certificate" and ec["cost_of_entry_lakh"] > 2.0:
        w.append(f"certificate tier but cost {ec['cost_of_entry_lakh']}L looks like a degree")
    if p["degree_dependency"] in ("undergrad", "professional") and ec["cost_of_entry_lakh"] < 1.0:
        w.append(f"{p['degree_dependency']} tier but cost only {ec['cost_of_entry_lakh']}L")

    # --- ai_exposure must be recomputable and agree with its own claims ---
    if sum(comp.values()) != 100:
        e.append(f"work_composition sums to {sum(comp.values())}")
    raw = comp["knowledge_retrievable"] + comp["skill_digital"]
    if ai["exposure_raw"] != raw:
        e.append(f"exposure_raw {ai['exposure_raw']} but composition gives {raw}")
    band = "high" if raw >= 65 else ("medium" if raw >= 40 else "low")
    if ai["legal_accountability"]:
        band = {"high": "medium", "medium": "low", "low": "low"}[band]
    if ai["band"] != band:
        e.append(f"band '{ai['band']}' but raw {raw} gives '{band}'")
    if comp["skill_physical"] >= 40 and ai["band"] != "low":
        w.append("heavily physical work but band is not low — check the split")
    if ai["band"] == "high" and not p["admin_review"]["required"]:
        e.append("ai_exposure high must carry admin_review")

    # --- the derived filter flag ---
    mid = ec["mid_career_midpoint"]
    expect = not (mid < RULES["mid_career_floor_lpa"]
                  or (mid < RULES["ai_penalty_clause"]["mid_career_below_lpa"]
                      and ai["band"] == RULES["ai_penalty_clause"]["when_ai_exposure"]))
    if p.get("filter") is not expect:
        e.append(f"filter is {p.get('filter')} but the rule gives {expect}")

    # --- narrative fields must not be empty or contradict structure ---
    if len(p["one_liner"]) > 110:
        w.append("one_liner too long to read at a glance")
    if not p["job_roles"]:
        e.append("no job_roles")
    if p["self_employment"] == "common" and p["degree_dependency"] == "undergrad" and ec["cost_of_entry_lakh"] > 8:
        w.append("expensive degree but flagged commonly self-employed — check")
    if p["after_undergrad"] == "masters_required" and p["degree_dependency"] == "certificate":
        e.append("masters_required makes no sense at certificate tier")
    if p["verification"]["status"] == "verified" and not p["verification"].get("source"):
        e.append("verified with no source")

    # --- role_spread: factors must be real, roles must exist on this profession ---
    rs = p.get("role_spread")
    if not rs:
        e.append("missing role_spread")
    else:
        dev = rs.get("deviating_roles", [])
        if rs.get("spread") not in ("narrow", "wide"):
            e.append(f"bad role_spread.spread '{rs.get('spread')}'")
        if (rs.get("spread") == "wide") != bool(dev):
            e.append(f"role_spread says '{rs.get('spread')}' but has {len(dev)} deviating group(s)")
        for gidx, g in enumerate(dev):
            for r in g.get("roles", []):
                if r not in p["job_roles"]:
                    e.append(f"role_spread[{gidx}] names role '{r}' which is not in job_roles")
            bad = [x for x in g.get("higher", []) + g.get("lower", []) if x not in FACTORS]
            if bad:
                e.append(f"role_spread[{gidx}] unknown psychometric factor(s) {bad}")
            if not g.get("higher") and not g.get("lower"):
                e.append(f"role_spread[{gidx}] deviates on no factor at all")
            if set(g.get("higher", [])) & set(g.get("lower", [])):
                e.append(f"role_spread[{gidx}] lists a factor as both higher and lower")
            if not g.get("why"):
                e.append(f"role_spread[{gidx}] has no explanation")

    # --- nuances must qualify a real field, and stay on the settled side of the line ---
    keys = set(p.keys()) | {"professional_sector"}
    for n in p.get("nuances", []):
        if n.get("field") not in keys:
            e.append(f"nuance names field '{n.get('field')}' which is not a key on this record")
        if not n.get("statement"):
            e.append("nuance with no statement")
        elif len(n["statement"]) < 40:
            w.append(f"nuance on '{n.get('field')}' is very short — is it really a nuance?")
        for hedge in ("not yet verified", "needs verification", "unverified", "confirm before"):
            if hedge in (n.get("statement") or "").lower():
                e.append(f"nuance on '{n['field']}' is unsettled — that belongs in admin_review, not nuances")

    return [f"{pid}: {x}" for x in e], [f"{pid}: {x}" for x in w]


def duplicate_job_roles():
    """The same job-role string under two professions is either a duplicate or an ambiguity.

    Caught 'Production Engineer' (Mechanical + Petroleum, different meanings) and
    'Process Safety Engineer' (Chemical + Fire & Safety) on its first run.
    """
    from collections import defaultdict
    seen = defaultdict(list)
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            for r in p["job_roles"]:
                seen[r.strip().lower()].append(f"{p['profession']} (S{d['professional_sector_id']})")
    return [f"'{r}' appears under: {', '.join(ps)}" for r, ps in sorted(seen.items()) if len(ps) > 1]


def reconcile():
    """Every routed_elsewhere promise must be KEPT once the target sector is built.

    Sector 1 says "UI/UX Designer goes to Sector 8". When Sector 8 exists, it must actually
    contain it. Unkept promises are how professions silently fall through the cracks.
    """
    sectors, built = {}, {}
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        n = d["professional_sector_id"]
        built[n] = d["professional_sector"]
        haystack = []
        for p in d["professions"]:
            haystack.append(p["profession"].lower())
            haystack += [r.lower() for r in p["job_roles"]]
        sectors[n] = (haystack, d)

    broken, pending = [], []
    for n, (_, d) in sorted(sectors.items()):
        for r in d.get("routed_elsewhere", []):
            target = int(r["goes_to"].split(".")[0])
            if target not in built:
                pending.append(f"S{n} -> S{target}: {r['profession']}")
                continue
            # All distinctive words must appear in ONE entry, not scattered across the sector.
            # "Computer Science Researcher" must not match "Research Scientist (Life Sciences)".
            name = r["profession"].lower().replace("/", " ")
            words = [w for w in name.split()
                     if len(w) > 3 and w not in ("scientist", "engineer", "analyst", "researcher",
                                                 "technician", "associate", "officer", "designer",
                                                 "manager", "specialist")]
            entries = sectors[target][0]
            if words:
                found = any(all(w in entry for w in words) for entry in entries)
            else:  # nothing distinctive survived — fall back to the whole name
                found = any(name.strip() in entry for entry in entries)
            if not found:
                broken.append(f"S{n} promised '{r['profession']}' to S{target} ({built[target]}) — NOT FOUND there")
    return broken, pending


def spec_drift():
    """Every key in the data must appear in the DECISIONS.md schema table, and vice versa.

    Documentation rot is silent. This makes it loud.
    """
    spec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    table = spec[spec.index("## 1. Profession schema"):spec.index("**Dropped after discussion:**")]
    documented = set(re.findall(r"^\| `([a-z0-9_]+)` \|", table, re.M))
    keys = set()
    for f in (ROOT / "data" / "professions").glob("*.json"):
        for p in json.loads(f.read_text(encoding="utf-8"))["professions"]:
            keys |= set(p.keys())
    return sorted(keys - documented), sorted(documented - keys)


def main():
    wanted = sys.argv[1:]
    files = sorted((ROOT / "data" / "professions").glob("*.json"))
    if wanted:
        files = [f for f in files if any(f.name.startswith(x) for x in wanted)]
    total_e = total_w = 0
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        errs, warns = [], []
        for p in d["professions"]:
            a, b = audit(p)
            errs += a
            warns += b
        total_e += len(errs)
        total_w += len(warns)
        print(f"\n{d['professional_sector']}  ({len(d['professions'])} professions)")
        print(f"  {len(errs)} error(s), {len(warns)} warning(s)")
        for x in errs:
            print(f"  ERROR  {x}")
        for x in warns:
            print(f"  warn   {x}")
    dups = duplicate_job_roles()
    if dups:
        print(f"\n{'=' * 60}\nDUPLICATE JOB ROLES ACROSS PROFESSIONS")
        for x in dups:
            print(f"  DUPLICATE  {x}")

    undoc, stale = spec_drift()
    if undoc or stale:
        print(f"\n{'=' * 60}\nSPEC DRIFT (DECISIONS.md section 1)")
        for k in undoc:
            print(f"  UNDOCUMENTED  data has '{k}' but the spec table does not")
        for k in stale:
            print(f"  STALE         spec documents '{k}' but no record has it")

    broken, pending = reconcile()
    print(f"\n{'=' * 60}\nCROSS-FILE RECONCILIATION")
    print(f"  {len(broken)} broken promise(s), {len(pending)} awaiting an unbuilt sector")
    for b in broken:
        print(f"  BROKEN  {b}")
    print(f"\ntotal: {total_e + len(broken)} error(s), {total_w} warning(s)")
    return 1 if (total_e or broken or undoc or stale or dups) else 0


if __name__ == "__main__":
    raise SystemExit(main())
