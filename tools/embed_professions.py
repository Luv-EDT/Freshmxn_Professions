"""STEP 5 — give every profession a stored meaning-vector (Voyage AI).

    python tools/embed_professions.py --dry-run   # what would change, no network, no key needed
    python tools/embed_professions.py             # embed only what changed
    python tools/embed_professions.py --force     # re-embed everything

Writes data/profession_embeddings.json, keyed by profession.id. GENERATED DATA — never
hand-edited, same rule as build/*.csv. It lives under data/ rather than build/ because Step 3
consumes it and a coverage audit must not depend on a directory the repo treats as disposable.

WHY voyage-4-large: this is a one-time index of 218 short documents. Volume is trivial, so the
quality tier costs almost nothing. The voyage-4 family SHARES ONE VECTOR SPACE, so a query path
can later use voyage-4-lite against these vectors with no re-indexing — the model is recorded on
every entry precisely so that promise can be checked rather than assumed.

The API is NOT OpenAI-compatible: its own JSON schema, and `input_type` is REQUIRED. Documents
being indexed take "document"; a search string typed by a user takes "query". Getting that wrong
silently degrades similarity rather than erroring, which is the worst failure mode available, so
it is passed explicitly at every call site and never defaulted.

IDEMPOTENT BY CONTENT HASH. Each entry stores a sha256 of the exact text embedded plus the model
name. A re-run embeds a profession only if that hash changed. This matters more than cost: the
taxonomy is edited constantly, and an index that silently drifts out of date is worse than one
that is obviously stale. `--dry-run` prints the drift without spending anything.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "professions"
OUT = ROOT / "data" / "profession_embeddings.json"

MODEL = "voyage-4-large"
ENDPOINT = "https://api.voyageai.com/v1/embeddings"
INPUT_TYPE = "document"
# voyage-4 models are Matryoshka-trained, so a 1024-d truncation is a real embedding rather than a
# lossy crop. 218 professions and a few hundred NCO titles is a tiny corpus — 2048 dimensions have
# nothing to separate that 1024 cannot, and they double a generated file sitting in a repo that is
# otherwise entirely hand-reviewed text. Chosen deliberately, not defaulted.
OUTPUT_DIMENSION = 1024
# Voyage accepts many texts per call, but an account with no payment method on file is capped at
# 3 REQUESTS PER MINUTE and 10K TOKENS PER MINUTE — and that is the account this index was built
# on. Batches of 64 ran ~4.7k tokens each and tripped the token cap on the third request.
# 32 texts is ~2.4k tokens, so three requests a minute sits at roughly 7k TPM: inside both caps
# with room to spare. Raise BATCH and lower PACE_SECONDS once billing is enabled.
BATCH = 32
PACE_SECONDS = 21.0  # 3 RPM is one request per 20s; 21 gives the server's clock a second of slack.
SCHEMA_VERSION = "1.0"


def embed_text(p):
    """The text that represents a profession in vector space.

    Name + one_liner + job roles, and nothing else. Deliberately EXCLUDES economics, verification
    and AI exposure: those are facts ABOUT the profession, not descriptions of the work, and
    mixing them in would pull salary-similar professions together in a space that is supposed to
    mean skill-and-purpose similarity. Step 3 asks 'is this occupation missing from our list',
    which is a question about work, so only the work is embedded.
    """
    roles = ", ".join(p["job_roles"])
    return f"{p['profession']}. {p['one_liner']} Job roles include: {roles}."


def content_hash(text):
    """Hash the MODEL and the DIMENSION with the text. Either one changing invalidates every
    vector even if no word of the source changed — a different model is a different space, and a
    different truncation is a different space too. Comparing across them is nonsense, so the hash
    has to notice.
    """
    return hashlib.sha256(
        f"{MODEL}\x00{OUTPUT_DIMENSION}\x00{text}".encode("utf-8")).hexdigest()


def load_professions():
    out = []
    for f in sorted(SRC.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d["professions"]:
            out.append((d["professional_sector_id"], d["professional_sector"], p))
    return out


def load_existing():
    if not OUT.exists():
        return {}
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    return {e["id"]: e for e in doc.get("embeddings", [])}


def call_voyage(texts, api_key, input_type=INPUT_TYPE, model=MODEL, retries=5):
    """One batch. Returns vectors in the SAME ORDER as `texts`.

    Order is not assumed — Voyage returns an `index` on every object and the response is sorted by
    it before returning. A silently permuted batch would attach 64 professions to the wrong
    meanings and no test in this repo would notice.
    """
    body = json.dumps({"input": texts, "model": model, "input_type": input_type,
                       "output_dimension": OUTPUT_DIMENSION}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    # 429 backoff starts ABOVE the rate-limit window, not below it. A 2s first retry against a
    # 3-RPM cap is guaranteed to fail again and just burns attempts — the first run exhausted all
    # five retries in 30 seconds without ever waiting long enough to succeed.
    delay = 25.0
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = json.loads(r.read().decode("utf-8"))
            data = sorted(payload["data"], key=lambda x: x["index"])
            if len(data) != len(texts):
                raise RuntimeError(f"asked for {len(texts)} vectors, got {len(data)}")
            return [d["embedding"] for d in data], payload.get("usage", {})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            # 429 and 5xx are worth waiting out; a 400 means the request is wrong and never will be.
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                print(f"    HTTP {e.code}, retry {attempt}/{retries} in {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Voyage HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            if attempt < retries:
                print(f"    network error ({e.reason}), retry {attempt}/{retries} in {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Voyage unreachable: {e.reason}") from None
    raise RuntimeError("unreachable")


def write_index(entries, profs, today, partial=False):
    """Write the index. Shared by the final write and the mid-run checkpoint.

    Returns (ok, dimensions). Ordered by sector then by the sector file's own order, so a diff
    between two runs is readable — a dict-ordered dump would reshuffle on every regeneration and
    make `git diff` useless for spotting what actually changed.
    """
    ordered = [entries[p["id"]] for _, _, p in profs if p["id"] in entries]
    dims = sorted({e["dimensions"] for e in ordered})
    if len(dims) != 1:
        print(f"! vectors have MIXED DIMENSIONS {dims} — the index is not comparable",
              file=sys.stderr)
        return False, None
    note = ("One vector per profession.id, built from name + one_liner + job_roles. The voyage-4 "
            "family shares a vector space, so a query path may use voyage-4-lite against these "
            "vectors without re-indexing — but it MUST pass input_type='query', not 'document'. "
            "Regenerate with tools/embed_professions.py; it re-embeds only professions whose "
            "source text changed.")
    if partial:
        note = ("PARTIAL INDEX — a run failed partway and this is what completed. Re-run "
                "tools/embed_professions.py to finish; it resumes rather than restarting. "
                "audit.py will report the missing ids until then. ") + note
    OUT.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "model": MODEL,
        "input_type": INPUT_TYPE,
        "dimensions": dims[0],
        "complete": not partial,
        "generated_on": today,
        "generated_by": "tools/embed_professions.py — do not hand-edit",
        "count": len(ordered),
        "note": note,
        "embeddings": ordered,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    return True, dims[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be embedded and exit; no network, no API key needed")
    ap.add_argument("--force", action="store_true", help="re-embed every profession")
    args = ap.parse_args()

    profs = load_professions()
    existing = load_existing()

    todo, unchanged = [], 0
    for sid, sname, p in profs:
        text = embed_text(p)
        h = content_hash(text)
        prev = existing.get(p["id"])
        if prev and prev.get("content_hash") == h and prev.get("model") == MODEL and not args.force:
            unchanged += 1
            continue
        todo.append((sid, sname, p, text, h, "new" if not prev else "changed"))

    stale = [e for e in existing if e not in {p["id"] for _, _, p in profs}]

    print(f"professions      {len(profs)}")
    print(f"already current  {unchanged}")
    print(f"to embed         {len(todo)}"
          + (f"  ({sum(1 for t in todo if t[5] == 'new')} new, "
             f"{sum(1 for t in todo if t[5] == 'changed')} changed)" if todo else ""))
    if stale:
        print(f"stale (no longer in the taxonomy, will be dropped): {len(stale)}  {stale}")

    if args.dry_run:
        for sid, _, p, text, _, why in todo[:10]:
            print(f"  [{why:<7}] S{sid:<3} {p['id']:<34} {len(text):>4} chars")
        if len(todo) > 10:
            print(f"  … and {len(todo) - 10} more")
        print("\ndry run — nothing written, no API call made")
        return 0

    if not todo and not stale:
        print("\nnothing to do — the index is current")
        return 0

    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        print("\n! VOYAGE_API_KEY is not set. Export it and re-run:", file=sys.stderr)
        print("!   PowerShell:  $env:VOYAGE_API_KEY = '…'", file=sys.stderr)
        print("!   bash:        export VOYAGE_API_KEY='…'", file=sys.stderr)
        print("! The key is read from the environment and never written to disk or to this repo.",
              file=sys.stderr)
        return 1

    today = __import__("datetime").date.today().isoformat()
    total_tokens = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        if i:
            time.sleep(PACE_SECONDS)
        print(f"  embedding {i + 1}-{i + len(chunk)} of {len(todo)} …", flush=True)
        try:
            vectors, usage = call_voyage([c[3] for c in chunk], api_key)
        except RuntimeError as err:
            # CHECKPOINT. The first run lost two completed batches to a failure in the third, and
            # paid for them again on the retry. Everything already embedded is written out before
            # the error propagates, so a re-run resumes instead of restarting — which is the whole
            # point of hashing the source text.
            if len(existing) > len(load_existing()):
                write_index(existing, profs, today, partial=True)
                print(f"\n! partial index saved — {len(existing)} vectors kept. Re-run to resume.",
                      file=sys.stderr)
            print(f"! {err}", file=sys.stderr)
            return 1
        total_tokens += usage.get("total_tokens", 0)
        for (sid, sname, p, text, h, _), vec in zip(chunk, vectors):
            existing[p["id"]] = {
                "id": p["id"],
                "profession": p["profession"],
                "professional_sector_id": sid,
                "professional_sector": sname,
                "model": MODEL,
                "input_type": INPUT_TYPE,
                "dimensions": len(vec),
                "embedded_from": text,
                "content_hash": h,
                "generated_on": today,
                "embedding": vec,
            }

    for gone in stale:
        del existing[gone]

    ok, dims = write_index(existing, profs, today)
    if not ok:
        return 1

    kb = OUT.stat().st_size // 1024
    print(f"\n{OUT.relative_to(ROOT).as_posix()}  ({len(existing)} vectors, {dims}-d, {kb} KB)")
    if total_tokens:
        print(f"tokens billed this run: {total_tokens:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
