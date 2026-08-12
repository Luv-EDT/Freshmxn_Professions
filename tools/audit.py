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
        # A licence is the USUAL source of personal legal accountability, not the only one.
        # A District Magistrate, a police officer and an army officer are personally answerable
        # under law by virtue of STATUTORY OFFICE, with no council licensing them. The claim still
        # has to be justified — it may not be asserted bare.
        if not any(n.get("field") in ("licensing_body", "ai_exposure") for n in p["nuances"]):
            e.append("claims legal_accountability with no licensing_body and no nuance saying "
                     "what the accountability rests on")

    # --- subject gates must agree with entrance exams and entry route ---
    gated = p["class12_prerequisite"] != "any"
    exams = p["entrance_exams"]
    has_exam = bool(exams.get("public_routes") or exams.get("private_entrances"))
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
    # A high band used to force an admin_review. It no longer does: ai_exposure SPEAKS FOR
    # ITSELF — the application reads the tag and frames the warning, and no human decision is
    # owed in the data. What the band must still carry is an explanation. See DECISIONS.md §8.45.
    if ai["band"] == "high" and not (ai.get("reason") or "").strip():
        e.append("ai_exposure high must give a reason")

    # --- the derived filter flag ---
    mid = ec["mid_career_midpoint"]
    # power_law records are exempt: their midpoint is arithmetic over a distribution with no
    # middle, and filtering on it deletes a profession on a number the record calls meaningless.
    # owner-income exemption: 'common' self-employment PLUS an open admin_review means the record
    # itself says the midpoint understates the profession. Filtering on it would delete a career on
    # a number we have already written down as incomplete.
    # It exempts the PAY FLOOR ONLY. Ownership says the figure is incomplete; it says nothing
    # about the work disappearing, so the AI clause still fires through it.
    owner_exempt = (p["self_employment"].get("likelihood") == "common"
                    and p["admin_review"]["required"])
    expect = ec.get("distribution") == "power_law" or not (
        (mid < RULES["mid_career_floor_lpa"] and not owner_exempt)
        or (mid < RULES["ai_penalty_clause"]["mid_career_below_lpa"]
            and ai["band"] == RULES["ai_penalty_clause"]["when_ai_exposure"]))
    if p.get("filter") is not expect:
        e.append(f"filter is {p.get('filter')} but the rule gives {expect}")

    # --- narrative fields must not be empty or contradict structure ---
    if len(p["one_liner"]) > 110:
        w.append("one_liner too long to read at a glance")
    if not p["job_roles"]:
        e.append("no job_roles")
    se = p["self_employment"]
    if se["likelihood"] == "common" and p["degree_dependency"] == "undergrad" and ec["cost_of_entry_lakh"] > 8:
        w.append("expensive degree but flagged commonly self-employed — check")
    # The ceiling is the number that stops the trades reading as dead ends. It is MONEY, so it
    # gets the same treatment as economics: sourced, or null and openly owed to a human.
    if se.get("ceiling_lpa"):
        v = se.get("verification") or {}
        if v.get("status") != "verified" or not (v.get("sources") or []):
            e.append("self_employment.ceiling_lpa is a money figure with no verified source")
        lo, hi = (se["ceiling_lpa"].split("-") + [None])[:2]
        try:
            if hi is not None and float(hi) <= ec["mid_career_midpoint"]:
                w.append("self-employment ceiling is not above employed mid-career — is it a ceiling?")
        except ValueError:
            e.append(f"self_employment.ceiling_lpa '{se['ceiling_lpa']}' is not a numeric range")
    elif (se["likelihood"] != "rare" and ec["mid_career_midpoint"] < 6.0
          and not p["admin_review"]["required"]):
        # Only demanded where the MISSING ceiling actively misleads — a low employed figure on a
        # profession people routinely go independent in. Doctor is self-employed too, but nobody
        # is misled by 31.5 LPA. Mason at 3.0 with no contractor figure is the whole problem.
        e.append(f"self_employment '{se['likelihood']}' at mid-career {ec['mid_career_midpoint']} "
                 f"with no ceiling_lpa must carry an admin_review — this is the case where the "
                 f"missing number makes the profession look like a dead end")
    if p["after_undergrad"] == "masters_required" and p["degree_dependency"] == "certificate":
        e.append("masters_required makes no sense at certificate tier")
    if p["verification"]["status"] == "verified" and not p["verification"].get("source"):
        e.append("verified with no source")
    # A record that says its own money is power-law or bimodal is describing an UNSETTLED schema
    # problem, which §9 says belongs to a human.
    if ec.get("distribution", "range") != "range" and not p["admin_review"]["required"]:
        e.append(f"economics.distribution is '{ec['distribution']}' but no admin_review is "
                 f"required — a midpoint that describes nobody is a decision owed to a human")

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


def structural_blocks():
    """The file-level blocks nothing was checking.

    `boundary_decisions_needing_your_signoff` held 18 entries that no tool ever surfaced, so they
    drifted: one still described Medical Coder as living in Sector 4 after it had been removed.
    A queue nobody prints is a queue nobody works.
    """
    e, counts = [], {"routed": 0, "merged": 0, "boundary": 0}
    everything = {}
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        everything[d["professional_sector_id"]] = {p["profession"] for p in d["professions"]}
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        n = d["professional_sector_id"]
        names = everything[n]
        for r in d.get("routed_elsewhere", []):
            counts["routed"] += 1
            for k in ("profession", "goes_to", "tag_here_instead", "why"):
                if not r.get(k):
                    e.append(f"S{n} routed_elsewhere '{r.get('profession')}' missing '{k}'")
            if r["profession"] in names:
                e.append(f"S{n} routes '{r['profession']}' away but still lists it as a profession")
        for m in d.get("merged_into", []):
            counts["merged"] += 1
            if m["merged_into"] not in names:
                e.append(f"S{n} merged '{m['profession']}' into '{m['merged_into']}', "
                         f"which does not exist in this sector")
            if m["profession"] in names:
                e.append(f"S{n} merged away '{m['profession']}' but still lists it")
        counts["boundary"] += len(d.get("boundary_decisions_needing_your_signoff", []))
    return e, counts


def preference_presets():
    """Report membership of the filter_rules presets so they cannot drift silently.

    The formal_workplace_track preset is how the application serves a student who wants a
    credentialed, non-manual career. It is derived at query time from fields on every record,
    so every new sector changes its membership without anyone touching it.
    """
    rules = json.loads((ROOT / "data" / "filter_rules.json").read_text(encoding="utf-8"))
    if "preference_filters" not in rules:
        return None
    kept, removed = [], []
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            credentialed = p["degree_dependency"] in ("undergrad", "professional")
            manual = p["ai_exposure"]["work_composition"]["skill_physical"] > 50
            # Government uniformed service is formal employment however physical it is.
            # Without this, Firefighter was removed from the formal-work filter for scoring 60
            # on skill_physical, which is exactly backwards.
            gov = ("EXT-GOVT" in p["industrial_sectors"]
                   and bool(p["entrance_exams"]["public_routes"]))
            (kept if (credentialed or not manual or gov) else removed).append(
                (p["profession"], p["ai_exposure"]["exposure_raw"]))
    return kept, removed


def entrance_gates():
    """The gate registry carries the numbers a family acts on. Validate them like money.

    A gate says how many people compete for how many places, how long preparation takes, and
    what a candidate holds if it fails. Every one of those can mislead, so each gets a rule.
    """
    reg = json.loads((ROOT / "data" / "entrance_gates.json").read_text(encoding="utf-8"))
    gates = reg["gates"]
    e = []
    for key, g in gates.items():
        a, s, stored = g.get("applicants_per_year"), g.get("seats_or_posts"), g.get("applicants_per_seat")
        if a and s:
            expect = round(a / s, 1)
            if stored is None or abs(stored - expect) > 0.05:
                e.append(f"gate '{key}': applicants_per_seat {stored} but {a}/{s} gives {expect}")
        elif stored is not None:
            e.append(f"gate '{key}': applicants_per_seat set without both applicants and seats")
        if g["mechanism"] == "attrition_limited" and g.get("pass_rate_percent") is None:
            e.append(f"gate '{key}': attrition_limited but no pass_rate_percent")
        if not (g.get("verification") or {}).get("source"):
            e.append(f"gate '{key}': no source — every figure here is one a family will act on")
        # A gate may never claim preparation is worth nothing.
        un = g.get("if_unsuccessful") or {}
        if not un.get("transfers_to"):
            e.append(f"gate '{key}': if_unsuccessful names nothing it transfers to. Preparation is "
                     f"never worth zero, and saying so misleads toward despair.")
        if not (un.get("non_credential_gain") or "").strip():
            e.append(f"gate '{key}': if_unsuccessful must say what is gained even when it fails")
        # Easier odds without the price is the misleading half of the truth.
        # alternative_to is OPTIONAL — a private gate may itself be the primary route into a
        # profession, which is the normal case in animation, culinary, sound engineering and much
        # of design. What must hold is that if it CLAIMS to be an alternative, the thing it is an
        # alternative to actually exists.
        alt = g.get("alternative_to")
        if alt and alt not in gates:
            e.append(f"gate '{key}': alternative_to '{alt}' is not in the registry")
        if g["type"] == "private_reputed" and g.get("typical_total_cost_lakh") is None:
            e.append(f"gate '{key}': private_reputed with no typical_total_cost_lakh — reporting "
                     f"easier odds without the cost tells a rich student the truth and a poor one a lie")

    used = set()
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            c = p.get("entry_competition") or {}
            if c.get("primary_gate"):
                used.add(c["primary_gate"])
            used |= set(c.get("alternative_gates") or [])
            if (c.get("alternative_gates") or []) and not c.get("primary_gate"):
                e.append(f"S{d['professional_sector_id']} {p['profession']}: names alternative "
                         f"gates with no primary_gate — a fallback shown without the main route. "
                         f"If the alternative IS the main route, make it the primary_gate.")
    # A gate reached only as another gate's next stage or alternative is still in use.
    linked = {g.get("next_stage") for g in gates.values()} | {g.get("alternative_to") for g in gates.values()}
    return e, sorted(set(gates) - used - {x for x in linked if x}), len(reg.get("pending_gates", []))


def money_sources():
    """A salary or fee figure may not rest on a page that contains no money.

    Sector 4 shipped all 20 economics blocks marked 'verified', citing the NEET eligibility
    page and the UGC list of professional councils. Neither carries a single rupee — the
    build script had pasted the ELIGIBILITY verification block onto the ECONOMICS block.
    Both tools passed it. Caught by hand on the third pass.

    Rule: a source registered in verified_facts.json may not be cited for economics UNLESS
    that fact itself carries money. The CSIR JRF page is registered as an eligibility fact but
    does state the stipend, so it is a legitimate economics source for Sector 3 — the check
    exempts it by looking for money words in the fact's own statement.
    """
    facts = json.loads((ROOT / "data" / "verified_facts.json").read_text(encoding="utf-8"))
    MONEY = ("stipend", "salary", "fee", "lakh", "crore", "rupee", "rs ", "pay", "wage")
    rules_pages = {x["source"] for x in facts["facts"]
                   if x.get("source") and not any(m in x["statement"].lower() for m in MONEY)}
    out = []
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            # Both money-bearing blocks get the same treatment.
            for label, v in (("economics", p["economics"].get("verification", {})),
                             ("self_employment.ceiling", p["self_employment"].get("verification") or {})):
                for s in v.get("sources") or []:
                    if s in rules_pages:
                        out.append(f"S{d['professional_sector_id']} {p['profession']}: {label} cites "
                                   f"{s} — that is a rules/eligibility source with no compensation data")
                if v.get("status") == "verified" and not (v.get("sources") or []):
                    out.append(f"S{d['professional_sector_id']} {p['profession']}: {label} claims "
                               f"verified with no source")
    return out


def orphaned_facts():
    """A verified fact nothing cites is a profession-shaped hole with a receipt attached.

    verified_facts.json carried jee-main-paper2b-bplan — "B.Planning requires Maths only" — and
    §4 used it as the WORKED EXAMPLE of the class12_prerequisite rule, while no profession in any
    of the eighteen sectors consumed it. Somebody had verified a fact for a career the taxonomy
    did not contain, and nothing noticed for eleven sectors.

    Reported, not errored: a fact may legitimately serve a gate, a sector note or a rule rather
    than a profession record. The point is that an orphan should have to be looked at.
    """
    facts = json.loads((ROOT / "data" / "verified_facts.json").read_text(encoding="utf-8"))
    cited = set()
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        blob = f.read_text(encoding="utf-8")
        for x in facts["facts"]:
            if x["key"] in blob or (x.get("source") and x["source"] in blob):
                cited.add(x["key"])
    # A fact may honestly belong to a GATE or to the industrial-sector roster rather than to any
    # one profession — the CAT eligibility rule is a property of CAT, not of Management Consultant.
    # Scan those files too, and match on the KEY as well as the URL: the first version matched
    # gates by source URL only, so citing a fact by key inside a gate still read as orphaned.
    for other in ("entrance_gates.json", "industrial_sectors.json"):
        blob = (ROOT / "data" / other).read_text(encoding="utf-8")
        for x in facts["facts"]:
            if x["key"] in blob or (x.get("source") and x["source"] in blob):
                cited.add(x["key"])
    return [x["key"] for x in facts["facts"] if x["key"] not in cited]


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
            # A slash names ONE thing TWO WAYS — "IT Project Manager / Scrum Master" is a single
            # promise, and landing either half keeps it. Treating the slash as a conjunction
            # required one job role to contain 'project' AND 'scrum' AND 'master', which no honest
            # title does, and reported two kept promises as broken.
            # Punctuation is not part of a word. "Teacher (government school)" tokenised to
            # '(government' and 'school)', neither of which appears in any honest job title, so a
            # promise that WAS kept — Sector 12 lists "Government School Teacher" — was reported
            # broken. Strip non-alphanumerics from both sides before comparing.
            entries = [re.sub(r"[^a-z0-9 ]", " ", e) for e in sectors[target][0]]
            found = False
            for alt in re.sub(r"[^a-z0-9 /]", " ", r["profession"].lower()).split("/"):
                # Within one alternative, ALL distinctive words must appear in ONE entry, so
                # "Computer Science Researcher" still cannot match "Research Scientist (Life Sciences)".
                words = [w for w in alt.split()
                         if len(w) > 3 and w not in ("scientist", "engineer", "analyst", "researcher",
                                                     "technician", "associate", "officer", "designer",
                                                     "manager", "specialist")]
                if words:
                    found = any(all(w in entry for w in words) for entry in entries)
                else:  # nothing distinctive survived — fall back to the whole alternative
                    found = any(alt.strip() in entry for entry in entries)
                if found:
                    break
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

    struct, counts = structural_blocks()
    if struct:
        print(f"\n{'=' * 60}\nSTRUCTURAL BLOCKS")
        for x in struct:
            print(f"  ERROR  {x}")

    pref = preference_presets()
    if pref:
        kept, removed = pref
        mk = sum(x[1] for x in kept) / max(len(kept), 1)
        mr = sum(x[1] for x in removed) / max(len(removed), 1)
        print(f"\n{'=' * 60}\nPREFERENCE PRESET  formal_workplace_track  (derived, stored nowhere)")
        print(f"  keeps {len(kept)}  ·  removes {len(removed)}")
        print(f"  mean AI exposure — kept {mk:.1f}  vs  removed {mr:.1f}"
              f"{'   <-- the filter removes the SAFER careers' if mr < mk else ''}")
        print(f"  removed: {', '.join(n for n, _ in sorted(removed, key=lambda x: x[1]))}")

    gate_errs, unused_gates, pending_gates = entrance_gates()
    if gate_errs:
        print("\n" + "=" * 60 + "\nENTRANCE GATE REGISTRY")
        for x in gate_errs:
            print(f"  ERROR  {x}")

    money = money_sources()
    if money:
        print(f"\n{'=' * 60}\nMONEY RESTING ON A NON-MONEY SOURCE")
        for x in money:
            print(f"  ERROR  {x}")

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
    orphans = orphaned_facts()
    if orphans:
        print(f"\n{'=' * 60}\nVERIFIED FACTS NOTHING CITES")
        print("  Somebody went and verified these, and no profession record consumes them.")
        print("  Usually a MISSING PROFESSION, and the cheapest coverage-gap signal there is —")
        print("  it found Urban & Regional Planner. See DECISIONS.md §10, correction 21.")
        for k in orphans:
            print(f"  ORPHAN  {k}")

    print(f"\n{'=' * 60}\nOPEN QUEUES")
    print(f"  {counts['boundary']} boundary decision(s) awaiting sign-off  ·  "
          f"{counts['routed']} routed  ·  {counts['merged']} merged")
    print(f"  {pending_gates} entrance gate(s) not yet sourced"
          + (f"  ·  unused in the registry: {', '.join(unused_gates)}" if unused_gates else ""))
    print(f"\ntotal: {total_e + len(broken) + len(money) + len(struct) + len(gate_errs)} error(s), "
          f"{total_w} warning(s)")
    return 1 if (total_e or broken or undoc or stale or dups or money or struct or gate_errs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
