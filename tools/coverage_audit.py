"""STEP 3 — what whole professions are the 218 missing?

    python tools/coverage_audit.py --dry-run     # no network; reports what it would embed
    python tools/coverage_audit.py               # embed NCO titles (cached), then audit
    python tools/coverage_audit.py --threshold 0.72

A taxonomy cannot see its own gaps. This compares every NCO-2015 occupation title against all 218
professions in vector space and reports the ones that are FAR FROM EVERYTHING WE HAVE.

    OUTPUT IS A REVIEW QUEUE. It adds nothing, edits nothing, and decides nothing.

That restraint is the whole design. NCO is far more granular than this repo — "Boiler, Tindal" is
a job role, "Elected Official, Union Government" is a post — so most distant titles are correctly
absent. The audit's job is to make a human LOOK, not to be right.

THREE THINGS IT DOES SO THE OUTPUT IS READABLE RATHER THAN TRUE-BUT-USELESS:

1. CLUSTERS. 400 loose titles is not a finding. Titles near each other are grouped, so the output
   reads "here is a missing neighbourhood" — twenty kinds of loom operator is ONE question.
2. CHECKS THE GRAVEYARD FIRST. Medical Coder was removed on purpose after a long argument. A tool
   that resurfaces it as "new" three days later is worse than no tool. Anything already routed or
   merged is labelled ALREADY DECIDED and sorted to the bottom.
3. PRINTS THE BOUNDARY. The threshold is a judgment call, not a fact, so the titles either side of
   it are printed for calibration instead of the cutoff being presented as objective.

KNOWN BLIND SPOT - READ THIS BEFORE TRUSTING A CLEAN RESULT:

    This audit finds gaps in vocabulary we DO NOT HAVE, and is blind to gaps in vocabulary we
    already have the wrong words for.

'Undertakers and Embalmers' surfaced easily - the nearest names we had were 'Butcher' and
'Wrestler', so the score collapsed and the hole was obvious. But:

    "Air Traffic Controller Specialist" -> 0.781  "Cargo Pilot"          reported as COVERED
    "Locomotive Driver"                 -> 0.856  "Truck Driver"         reported as COVERED
    "Model, Fashion"                    -> 0.845  "Fashion Designer"     reported as COVERED

An air traffic controller does not fly the plane, a loco pilot is not a truck driver, and a model
is not a designer. Those scores are high because the DOMAIN VOCABULARY overlaps, and cosine
similarity cannot distinguish shared words from shared work. All three were real gaps, and all
three were found by a human reading a list, not by this tool.

So: a clean run is a FLOOR on what is missing, never a ceiling. See DECISIONS.md 10, correction 26.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_professions import MODEL, OUTPUT_DIMENSION, PACE_SECONDS, call_voyage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROF_VECTORS = ROOT / "data" / "profession_embeddings.json"
NCO_TITLES = ROOT / "data" / "nco_2015_titles.json"
NCO_VECTORS = ROOT / "data" / "nco_2015_embeddings.json"
SURFACE_VECTORS = ROOT / "data" / "surface_embeddings.json"
OUT = ROOT / "build" / "coverage_gaps.json"

# A title whose best match is below this is a candidate gap. NOT A FACT — a dial. 0.75 is the
# starting point the plan specified; --threshold moves it and the boundary print exists to argue
# with it. Everything downstream reports the value it ran at.
THRESHOLD = 0.75
# Two candidate titles this close to each other are the same neighbourhood.
CLUSTER_AT = 0.72
# An account with no payment method is capped at 3 RPM / 10K TPM. NCO titles are ~8 tokens each,
# so batching by TOKEN BUDGET rather than by count sends ~300 titles per request instead of 32 —
# the whole list in about a dozen requests rather than a hundred.
TOKEN_BUDGET = 2800
CHARS_PER_TOKEN = 4


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def surface_strings():
    """Every NAME this taxonomy exposes: 218 profession names + 1,639 job roles, each tagged with
    the profession it belongs to.

    THIS IS WHAT NCO TITLES ARE COMPARED AGAINST, and it replaced comparing them to the profession
    documents in data/profession_embeddings.json. That first design was wrong in a way worth
    recording, because the numbers it produced looked plausible:

      A 2-word NCO title ("Miller") and a 250-character profession document are texts of wildly
      different LENGTH and SPECIFICITY. Cosine between them is depressed by that asymmetry alone,
      independently of meaning, so 2,997 of 3,128 titles fell below the planned 0.75 and the
      "most missing" occupations came back as 'Lac Treater -> Lawyer' and 'Miller -> Lawyer'.
      Those are not gaps. They are what a similarity score does when it has nothing to work with
      and must still return its best guess.

    Title-against-title is symmetric, and it also asks the question we actually mean: NOT "is this
    occupation semantically near our description of a profession" but "IS THIS OCCUPATION ALREADY
    ONE OF THE NAMES WE LIST?" — the same question tools/probe.py asks by string match, done in
    meaning-space so 'Auto Service Technician' can find 'Automobile Mechanic'.
    """
    out = []
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            out.append({"text": p["profession"], "kind": "profession", "id": p["id"],
                        "profession": p["profession"], "sector": d["professional_sector"]})
            for r in p["job_roles"]:
                out.append({"text": r, "kind": "job_role", "id": p["id"],
                            "profession": p["profession"], "sector": d["professional_sector"]})
    return out


def load_professions():
    doc = json.loads(PROF_VECTORS.read_text(encoding="utf-8"))
    if not doc.get("complete", True):
        print("! the profession index is PARTIAL — finish tools/embed_professions.py first",
              file=sys.stderr)
        raise SystemExit(1)
    if doc["model"] != MODEL or doc["dimensions"] != OUTPUT_DIMENSION:
        print(f"! profession index is {doc['model']}/{doc['dimensions']}-d but this tool embeds "
              f"queries with {MODEL}/{OUTPUT_DIMENSION}-d. Comparing across vector spaces is "
              f"meaningless — re-run tools/embed_professions.py --force.", file=sys.stderr)
        raise SystemExit(1)
    return doc["embeddings"]


def load_graveyard():
    """Professions already considered and deliberately not kept — routed out, or merged away."""
    out = []
    for f in sorted((ROOT / "data" / "professions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d.get("routed_elsewhere", []):
            out.append(("ROUTED", r["profession"], f"{d['professional_sector']} -> {r['goes_to']}",
                        r["why"]))
        for m in d.get("merged_into", []):
            out.append(("MERGED", m["profession"], f"into {m['merged_into']}", m["why"]))
    return out


def title_hash(text):
    return hashlib.sha256(
        f"{MODEL}\x00{OUTPUT_DIMENSION}\x00{text}".encode("utf-8")).hexdigest()


def embed_strings(items, path, label, dry_run, what):
    """Embed a list of short strings, cached by content hash, checkpointed every batch.

    input_type='document' on BOTH sides deliberately. Voyage trains 'query' and 'document'
    asymmetrically; using 'query' on one side of a comparison that is symmetric in meaning would
    tilt every score in a direction nobody could later explain or reproduce.
    """
    cache = {}
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("model") == MODEL and doc.get("dimensions") == OUTPUT_DIMENSION:
            cache = {e["key"]: e for e in doc["embeddings"]}

    todo = [i for i in items if cache.get(i["key"], {}).get("content_hash")
            != title_hash(i["text"])]
    print(f"{label:<16} {len(items)}   already embedded {len(items) - len(todo)}   "
          f"to embed {len(todo)}")
    if dry_run or not todo:
        return cache, len(todo)

    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        print("\n! VOYAGE_API_KEY is not set — export it and re-run", file=sys.stderr)
        raise SystemExit(1)

    batches, cur, cur_tokens = [], [], 0
    for t in todo:
        est = max(1, len(t["text"]) // CHARS_PER_TOKEN)
        if cur and cur_tokens + est > TOKEN_BUDGET:
            batches.append(cur)
            cur, cur_tokens = [], 0
        cur.append(t)
        cur_tokens += est
    if cur:
        batches.append(cur)

    today = __import__("datetime").date.today().isoformat()
    done = 0
    for i, batch in enumerate(batches):
        if i:
            time.sleep(PACE_SECONDS)
        print(f"  embedding batch {i + 1}/{len(batches)} ({len(batch)} {what}) ...", flush=True)
        vectors, _ = call_voyage([b["text"] for b in batch], api_key)
        for b, vec in zip(batch, vectors):
            cache[b["key"]] = {**b, "content_hash": title_hash(b["text"]), "embedding": vec}
        done += len(batch)
        path.write_text(json.dumps({
            "model": MODEL, "dimensions": OUTPUT_DIMENSION, "input_type": "document",
            "generated_on": today, "generated_by": "tools/coverage_audit.py — do not hand-edit",
            "count": len(cache), "complete": done == len(todo),
            "note": f"Vectors for {what}, used only by the Step 3 coverage audit. Checkpointed "
                    f"after every batch so a rate-limit failure resumes rather than restarts.",
            "embeddings": list(cache.values()),
        }, ensure_ascii=False) + "\n", encoding="utf-8")
    return cache, len(todo)


def group_by_family(scored, threshold):
    """Group candidates by their NCO-2015 4-digit OCCUPATION FAMILY.

    This replaced single-link vector clustering, which was wrong twice over and worth recording:

      1. IT CHAINED. Single-link merges A and C whenever some B sits between them, and short job
         titles all sit between each other. At 0.72 it put 624 of 813 candidates in one cluster;
         loosening the threshold made it worse, not better — 811 of 813 by 0.56. A "cluster" of
         624 unrelated titles is not a missing neighbourhood, it is a failed algorithm.
      2. THE PARAMETER WAS MINE. Any cutoff I pick is a number I invented, which is exactly what
         this repo forbids everywhere else. NCO already groups its own occupations into 433
         families, published by the Ministry — an authoritative grouping, free, and the same one a
         labour statistician would use.

    A family where MOST titles are far from everything we list is the real signal: not "we are
    missing this job title" but "we do not cover this kind of work at all". Coverage ratio is
    reported next to family size so a 2-title family cannot masquerade as a 40-title one.
    """
    fams = {}
    for s in scored:
        f = fams.setdefault(s["family"], {"family": s["family"], "family_name": s["family_name"],
                                          "total": 0, "uncovered": [], "best": 0.0})
        f["total"] += 1
        f["best"] = max(f["best"], s["similarity"])
        if s["similarity"] < threshold:
            f["uncovered"].append(s)
    out = []
    for f in fams.values():
        if not f["uncovered"]:
            continue
        f["uncovered_count"] = len(f["uncovered"])
        f["coverage_ratio"] = round(1 - len(f["uncovered"]) / f["total"], 3)
        f["mean_similarity"] = round(
            sum(x["similarity"] for x in f["uncovered"]) / len(f["uncovered"]), 4)
        out.append(f)
    # Wholly-uncovered families first, then by how many titles they contain: a family we cover
    # 0% of is a different finding from one we cover 80% of, however large it is.
    out.sort(key=lambda f: (f["coverage_ratio"], -f["uncovered_count"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--include-residual", action="store_true",
                    help="also test the '…, Other' catch-all buckets (they describe no work)")
    args = ap.parse_args()

    load_professions()  # validates the profession index is complete and in the same vector space
    doc = json.loads(NCO_TITLES.read_text(encoding="utf-8"))
    titles = [{"key": t["code"], "text": t["title"], "code": t["code"], "title": t["title"],
               "family": t["family"], "family_name": t["family_name"] or f"Family {t['family']}"}
              for t in doc["titles"] if args.include_residual or not t["residual"]]
    surface = [{**s, "key": f"{s['id']}||{s['text']}"} for s in surface_strings()]

    ncache, npend = embed_strings(titles, NCO_VECTORS, "NCO titles", args.dry_run, "NCO titles")
    scache, spend = embed_strings(surface, SURFACE_VECTORS, "our names", args.dry_run,
                                  "profession names and job roles")
    if args.dry_run:
        print("\ndry run - nothing written, no API call made")
        return 0
    if {t["key"] for t in titles} - set(ncache) or {s["key"] for s in surface} - set(scache):
        print("! some strings are still unembedded - re-run to resume", file=sys.stderr)
        return 1

    sv = [(s, scache[s["key"]]["embedding"]) for s in surface]
    scored = []
    for t in titles:
        vec = ncache[t["key"]]["embedding"]
        best, bestsim = None, -1.0
        for s, svec in sv:
            c = cosine(vec, svec)
            if c > bestsim:
                best, bestsim = s, c
        scored.append({"code": t["code"], "title": t["title"],
                       "family": t["family"], "family_name": t["family_name"],
                       "matched_name": best["text"], "matched_kind": best["kind"],
                       "nearest": best["profession"], "nearest_id": best["id"],
                       "sector": best["sector"], "similarity": round(bestsim, 4)})
    scored.sort(key=lambda x: x["similarity"])

    cands = [s for s in scored if s["similarity"] < args.threshold]
    fams = group_by_family(scored, args.threshold)

    grave = load_graveyard()
    out_clusters = []
    for f in fams:
        blob = (f["family_name"] + " " + " ".join(x["title"] for x in f["uncovered"])).lower()
        decided = [{"kind": k, "profession": p, "where": w, "why": y}
                   for k, p, w, y in grave
                   if any(tok in blob for tok in p.lower().split() if len(tok) > 4)]
        out_clusters.append({
            "nco_family": f["family"],
            "label": f["family_name"],
            "family_size": f["total"],
            "uncovered": f["uncovered_count"],
            "coverage_ratio": f["coverage_ratio"],
            "best_similarity_in_family": round(f["best"], 4),
            "mean_similarity": f["mean_similarity"],
            "nearest_professions": sorted({x["nearest"] for x in f["uncovered"]}),
            "closest_names_we_have": sorted({x["matched_name"] for x in f["uncovered"]})[:8],
            "already_decided": decided,
            "titles": [{"code": x["code"], "title": x["title"], "nearest": x["nearest"],
                        "matched_name": x["matched_name"], "similarity": x["similarity"]}
                       for x in sorted(f["uncovered"], key=lambda y: y["similarity"])],
        })

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_on": __import__("datetime").date.today().isoformat(),
        "generated_by": "tools/coverage_audit.py — A REVIEW QUEUE, NOT A DECISION",
        "reference_set": doc["classification"],
        "reference_source": doc["source"],
        "model": MODEL, "dimensions": OUTPUT_DIMENSION,
        "threshold": args.threshold,
        "grouping": "NCO-2015 4-digit occupation family (the reference set's own structure)",
        "note": "Every entry is a QUESTION for a human. NCO-2015 is far more granular than this "
                "taxonomy — most distant titles are job roles, posts or trade specialisations that "
                "are correctly absent, and a cluster is only interesting if it fails the "
                "profession test in DECISIONS.md §8.95: affinity for a sector's object of concern, "
                "a separate skill set, and a need that exists in society. Clusters with a "
                "non-empty already_decided were considered and deliberately dropped — reversing "
                "one means reading the sector changelog first.",
        "counts": {
            "nco_titles_tested": len(titles),
            "below_threshold": len(cands),
            "families_touched": len(out_clusters),
            "families_wholly_uncovered": sum(1 for c in out_clusters if c["coverage_ratio"] == 0.0),
            "families_already_decided": sum(1 for c in out_clusters if c["already_decided"]),
        },
        "boundary_sample": scored[max(0, len(cands) - 15):len(cands) + 15],
        "families": out_clusters,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"\n{'=' * 68}\nCOVERAGE AUDIT  (threshold {args.threshold}, {len(titles)} NCO titles)")
    whole = [c for c in out_clusters if c["coverage_ratio"] == 0.0]
    print(f"  below threshold  {len(cands)} of {len(titles)} titles, touching "
          f"{len(out_clusters)} of {len(doc['families'])} NCO families")
    print(f"  families we cover NOTHING of: {len(whole)}")
    print(f"\n  TIGHTEST COVERAGE - NCO titles our taxonomy already answers well:")
    for s in scored[-5:][::-1]:
        print(f"    {s['similarity']:.3f}  {s['title'][:44]:<46} -> {s['nearest']}")
    print(f"\n  THE BOUNDARY — either side of {args.threshold}, for calibration:")
    for s in scored[max(0, len(cands) - 6):len(cands) + 6]:
        mark = "GAP " if s["similarity"] < args.threshold else "kept"
        print(f"    [{mark}] {s['similarity']:.3f}  {s['title'][:40]:<42} -> {s['nearest']}")
    print(f"\n  WHOLLY UNCOVERED NCO FAMILIES - nothing we list comes near ANY of their titles.")
    print(f"  This is the finding. One distant job title is noise; an entire official occupation")
    print(f"  family with zero coverage is a question worth a human's time.")
    for c in whole[:20]:
        flag = "  [ALREADY DECIDED]" if c["already_decided"] else ""
        print(f"    {c['uncovered']:>3}/{c['family_size']:<3} ~{c['mean_similarity']:.3f}  "
              f"{c['nco_family']}  {c['label'][:42]}{flag}")
    print(f"\n  PARTIALLY COVERED, most-uncovered first - we have SOME of this family:")
    for c in [x for x in out_clusters if x["coverage_ratio"] > 0.0][:8]:
        print(f"    {c['uncovered']:>3}/{c['family_size']:<3} cov {c['coverage_ratio']:.2f}  "
              f"{c['nco_family']}  {c['label'][:42]}")
    print(f"\n{OUT.relative_to(ROOT).as_posix()}  — review queue, nothing was added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
