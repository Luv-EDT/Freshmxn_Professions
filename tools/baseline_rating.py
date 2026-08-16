"""STEP 4 — merge scored samples into data/baseline_rating.json, and police them.

    python tools/baseline_rating.py --merge scratchpad/ratings_pass*.json
    python tools/baseline_rating.py --status

THE PSYCHOMETRIC LAYER IS KEPT OUT OF THE TAXONOMY, DELIBERATELY. It joins on `profession.id`, the
same fetch-once-reuse pattern as entrance_gates.json and verified_facts.json, because the two have
different lifecycles: the taxonomy is verification-gated and changes slowly, these scores are
judgment-generated and get refreshed on a mentor cadence. Merging them into the sector files would
tie a slow, sourced thing to a fast, unsourced one.

WHAT IS ACTUALLY SCORED, per profession, three times:
  factors  19 scores 1-10  — how much the WORK demands each factor, against data/factor_anchors.json
  weights  19 values 0-1   — how RELEVANT that factor is to this profession. This is what lets an
                             irrelevant factor drop OUT of matching instead of diluting it: musical
                             is 0.0 for a civil engineer, not 1/10 of a vote.
  drivingReasons 1-3       — from a CLOSED set of seven. Never invented.

RELIABILITY, and its honest limit. Three samples are averaged and any factor whose samples spread
more than MAX_SPREAD points is flagged into admin_review rather than quietly averaged — a
disagreement is information, and averaging it away destroys the only signal that says "this one
needs a human". But three passes by ONE model are less independent than three API calls to
different ones: correlated error is likely and the variance figure understates true uncertainty.
That limitation is written into every record rather than left for someone to discover.
"""

import argparse
import glob
import json
import statistics
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "baseline_rating.json"

FACTORS = [f["slug"] for g in json.loads(
    (ROOT / "data" / "psychometric_factors.json").read_text(encoding="utf-8"))["groups"]
    for f in g["factors"]]

# CLOSED SET. Never invented, never extended without a decision — the whole point of a fixed
# vocabulary is that 223 records tag the same idea the same way.
DRIVING_REASONS = {
    "curiosityDriven": "pursued mainly to explore, learn or understand something for its own sake "
                       "— the pull is 'I want to find out'.",
    "individualInternalProblems": "driven by resolving one's own inner struggles, growth wounds or "
                                  "personal demons through the work.",
    "interpersonalInternalProblems": "driven by fixing or navigating relationships and emotional "
                                     "dynamics between people.",
    "externalProblems": "driven by solving concrete real-world problems out in the world — "
                        "technical, social, environmental, systemic.",
    "personalGrowth": "pursued to build oneself — mastery, discipline, becoming more capable over "
                      "time.",
    "socialRecognition": "driven by status, being seen, respected, admired or validated by others.",
    "effortlessEngagement": "pursued because it produces flow with little friction — the work draws "
                            "on factors the student is naturally strong in, so it feels easy and "
                            "natural rather than effortful. Low resistance plus high absorption; "
                            "not external reward, not problem-solving, but FIT between innate "
                            "strengths and what the work demands.",
}

MAX_SPREAD = 2          # samples differing by more than this on any factor -> admin_review
BIG_JUMP = 2            # change vs the previous version this large -> admin_review on refresh
SCHEMA_VERSION = "1.0"


def professions():
    out = OrderedDict()
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            out[p["id"]] = (d["professional_sector_id"], d["professional_sector"], p["profession"])
    return out


def check_sample(pid, s, errs):
    """A malformed sample must never reach the average."""
    # SCORES ARE 0-10, NOT 1-10. The Step 4 brief said 1-10 and the rubric it also specified is
    # banded 0-2 / 3-4 / 5-6 / 7-8 / 9-10 — a 0-10 scale. The bands win, and the reason is not
    # pedantry: musical demand in a data engineer's work is ZERO, and forcing it to 1 asserts a
    # trace of musical requirement that does not exist. The weight already removes the factor from
    # matching; the score should still say the true thing. Caught by this validator on the first
    # merge, which is what it is for.
    for block, lo, hi in (("factors", 0, 10), ("weights", 0.0, 1.0)):
        got = s.get(block) or {}
        missing = [f for f in FACTORS if f not in got]
        unknown = [f for f in got if f not in FACTORS]
        if missing:
            errs.append(f"{pid}: {block} missing {len(missing)} — {', '.join(missing[:4])}")
        if unknown:
            errs.append(f"{pid}: {block} has unknown factor(s) {', '.join(unknown)}")
        for k, v in got.items():
            if not isinstance(v, (int, float)) or not (lo <= v <= hi):
                errs.append(f"{pid}: {block}.{k} = {v!r}, must be {lo}-{hi}")
    dr = s.get("drivingReasons") or []
    if not 1 <= len(dr) <= 3:
        errs.append(f"{pid}: drivingReasons has {len(dr)}, must be 1-3")
    for r in dr:
        if r not in DRIVING_REASONS:
            errs.append(f"{pid}: drivingReasons '{r}' is not in the closed set")
    if len(set(dr)) != len(dr):
        errs.append(f"{pid}: drivingReasons repeats a value")


def merge(paths):
    known = professions()
    passes = []
    for path in paths:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        passes.append(doc["ratings"])
        print(f"  {Path(path).name}: {len(doc['ratings'])} professions")

    errs, entries = [], []
    ids = [i for i in known if all(i in p for p in passes)]
    partial = [i for i in known if any(i in p for p in passes) and i not in ids]
    for pid in partial:
        errs.append(f"{pid}: scored in some passes but not all — refusing to average a partial set")

    for pid in ids:
        samples = [p[pid] for p in passes]
        for s in samples:
            check_sample(pid, s, errs)
        sid, sname, pname = known[pid]

        factors, weights, variance, wide = OrderedDict(), OrderedDict(), OrderedDict(), []
        for f in FACTORS:
            vals = [s["factors"][f] for s in samples if f in s.get("factors", {})]
            if not vals:
                continue
            spread = max(vals) - min(vals)
            factors[f] = round(statistics.mean(vals), 2)
            variance[f] = {"samples": vals, "spread": spread}
            if spread > MAX_SPREAD:
                wide.append(f"{f} (samples {vals}, spread {spread})")
            wv = [s["weights"][f] for s in samples if f in s.get("weights", {})]
            weights[f] = round(statistics.mean(wv), 2) if wv else 0.0

        # majority pick; a tie is a disagreement, not something to break arbitrarily
        counts = {}
        for s in samples:
            for r in s.get("drivingReasons", []):
                counts[r] = counts.get(r, 0) + 1
        majority = sorted([r for r, c in counts.items() if c >= 2],
                          key=lambda r: (-counts[r], r))[:3]
        tie = not majority and bool(counts)
        if not majority:
            majority = sorted(counts, key=lambda r: (-counts[r], r))[:1]

        reasons = []
        if wide:
            reasons.append(f"THE THREE SAMPLES DISAGREED by more than {MAX_SPREAD} points on: "
                           f"{'; '.join(wide)}. Averaged for now, but a disagreement this wide "
                           f"means the anchors do not settle this profession and a human should "
                           f"decide.")
        if tie:
            reasons.append("drivingReasons had NO majority across the three samples — every "
                           "candidate appeared once. The single reason stored is the first "
                           "alphabetically among the tied set and should not be trusted.")

        entries.append(OrderedDict([
            ("id", pid), ("profession", pname),
            ("professional_sector_id", sid), ("professional_sector", sname),
            ("factors", factors), ("weights", weights),
            ("drivingReasons", majority),
            ("samples", len(samples)),
            ("sample_variance", variance),
            ("version", SCHEMA_VERSION),
            ("generated_on", __import__("datetime").date.today().isoformat()),
            ("review_status", "unreviewed"),
            ("admin_review", OrderedDict([
                ("required", bool(reasons)),
                ("priority", "high" if wide else ("medium" if tie else "none")),
                ("reason", " ".join(reasons) or None)])),
        ]))

    if errs:
        print(f"\n! {len(errs)} error(s) — nothing written:")
        for e in errs[:25]:
            print(f"  ! {e}")
        return 1

    prev = {}
    if OUT.exists():
        prev = {e["id"]: e for e in json.loads(OUT.read_text(encoding="utf-8"))["ratings"]}
    jumped = 0
    for e in entries:
        old = prev.get(e["id"])
        if not old:
            continue
        moved = [f for f in FACTORS
                 if f in old["factors"] and abs(old["factors"][f] - e["factors"][f]) > BIG_JUMP]
        if moved:
            jumped += 1
            e["admin_review"] = OrderedDict([
                ("required", True), ("priority", "high"),
                ("reason", (e["admin_review"]["reason"] or "") +
                 f" REFRESH MOVED THIS RECORD by more than {BIG_JUMP} points on "
                 f"{', '.join(moved)}. A jump that large is either a real correction or a drifted "
                 f"scale; it does not go live until a human says which.")])

    OUT.write_text(json.dumps(OrderedDict([
        ("schema_version", SCHEMA_VERSION),
        ("generated_on", __import__("datetime").date.today().isoformat()),
        ("generated_by", "tools/baseline_rating.py — GENERATED, joins to the taxonomy on "
                         "profession.id. Never hand-edit; re-merge the samples."),
        ("joins_to", "data/professions/*.json by `id`"),
        ("rubric", "data/factor_anchors.json"),
        ("samples_per_profession", len(passes)),
        ("max_spread_before_review", MAX_SPREAD),
        ("driving_reasons_vocabulary", DRIVING_REASONS),
        ("known_limitation",
         "The three samples come from ONE model scoring the same rubric three times, not from "
         "three independent raters. Correlated error is likely and sample_variance therefore "
         "UNDERSTATES true uncertainty — a factor all three passes agree on may still be wrong "
         "together. Treat low variance as 'the rubric was unambiguous', never as 'this is "
         "correct'. Every record starts review_status: unreviewed for that reason."),
        ("counts", {"rated": len(entries),
                    "of_total": len(known),
                    "admin_review_required": sum(1 for e in entries if e["admin_review"]["required"]),
                    "moved_on_refresh": jumped}),
        ("ratings", entries),
    ]), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    c = json.loads(OUT.read_text(encoding="utf-8"))["counts"]
    print(f"\n{OUT.relative_to(ROOT).as_posix()}")
    print(f"  rated {c['rated']} of {c['of_total']}  ·  "
          f"{c['admin_review_required']} need review  ·  {c['moved_on_refresh']} moved on refresh")
    return 0


def status():
    known = professions()
    if not OUT.exists():
        print(f"no ratings yet — 0 of {len(known)}")
        return 0
    d = json.loads(OUT.read_text(encoding="utf-8"))
    rated = {e["id"] for e in d["ratings"]}
    print(f"rated {len(rated)} of {len(known)}")
    missing = [f"S{known[i][0]:<3}{known[i][2]}" for i in known if i not in rated]
    for m in missing[:20]:
        print(f"  todo  {m}")
    if len(missing) > 20:
        print(f"  … and {len(missing) - 20} more")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merge", nargs="+", metavar="GLOB")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.status or not args.merge:
        return status()
    paths = sorted({p for g in args.merge for p in glob.glob(g)})
    if not paths:
        print("! no sample files matched")
        return 1
    return merge(paths)


if __name__ == "__main__":
    raise SystemExit(main())
