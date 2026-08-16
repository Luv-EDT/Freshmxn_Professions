"""Extract the NCO-2015 occupation titles from the official DGE PDF into data/nco_2015_titles.json.

    python tools/nco_titles.py <path-to-National_Classification_of_Occupations_Vol_I-2015.pdf>

WHY THIS EXISTS: Step 3 asks "what whole professions are we missing?" and that question cannot be
answered from inside the taxonomy — a list cannot see its own gaps. It needs an external ground
truth, and India's is the National Classification of Occupations, maintained by the Directorate
General of Employment, Ministry of Labour & Employment.

SOURCE, and why this one:
  https://dge.gov.in/sites/default/files/2024-05/National_Classification_of_Occupations_Vol_I-2015.pdf
Volume I is the Code Structure volume; its Concordance Table prints every 8-digit NCO-2015 code
against its occupation title, which is the only machine-parseable form of the list that exists.
There is no CSV or API — the Ministry publishes PDFs. A state-government mirror
(employment.kerala.gov.in) carries the same document and was opened first; the DGE original is
used because a mirror is not a source. Both were checked and agree.

WHAT IT IS NOT: NCO titles are not professions in this repo's sense. "Boiler, Tindal" is a job
role; "Elected Official, Union Government" is a post. The list is far more granular than our 218
and deliberately so — it exists for employment exchanges to code individual vacancies. It is used
here ONLY as a completeness check: an occupation far from everything we have is a QUESTION, not an
instruction. See DECISIONS.md §8.95 for what actually earns a place as a profession.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "nco_2015_titles.json"
SOURCE = ("https://dge.gov.in/sites/default/files/2024-05/"
          "National_Classification_of_Occupations_Vol_I-2015.pdf")


def parse(pdf_path):
    try:
        from pypdf import PdfReader
    except ImportError:
        print("! needs pypdf:  pip install pypdf", file=sys.stderr)
        raise SystemExit(1)

    reader = PdfReader(pdf_path)
    full = "\n".join((page.extract_text() or "") for page in reader.pages)

    # NCO groups its own occupations into 4-digit FAMILIES, printed as "Family 8182 Steam Engine
    # and Boiler Operators". Capturing them means the coverage audit can report gaps in the
    # reference set's OWN structure instead of inventing a clustering hyperparameter — an
    # authoritative grouping beats a tuned one, and it is the same grouping a labour statistician
    # would use.
    families = {}
    for m in re.finditer(r"Family\s+(\d{4})\s+([^\n]+)", full):
        name = re.sub(r"\s+", " ", m.group(2)).strip(" .;:")
        if len(name) > 3 and m.group(1) not in families:
            families[m.group(1)] = name

    titles, seen_order = {}, []
    for line in full.split("\n"):
        m = re.match(r"\s*(\d{4})\.(\d{4})\s+(.*)$", line)
        if not m:
            continue
        code = f"{m.group(1)}.{m.group(2)}"
        title = m.group(3)
        # Each concordance row ends with the OLD NCO-2004 code the title maps to. Strip it, or
        # every title carries a stray number into the embedding.
        title = re.sub(r"\s*\d{4}\.\d{2}\s*$", "", title)
        title = re.sub(r"\s+", " ", title).strip(" .;:")
        # The introduction walks through 8153.0111 as a worked EXAMPLE, in prose, before the table
        # starts. Those lines match the row pattern and are not data.
        if len(title) < 3 or title.startswith("("):
            continue
        if title.lower().startswith(("job title", "occupation", "denotes")):
            continue
        if code not in titles:
            titles[code] = title
            seen_order.append(code)

    # Codes ending .9900 are "…, Other" residual buckets closing each family. They are real parts
    # of the classification and useless as occupations to compare against — "Legislators, Other"
    # describes no work. Kept, flagged, and excluded from the gap search by default.
    entries = [{"code": c, "title": titles[c], "residual": c.endswith(".9900"),
                "family": c[:4], "family_name": families.get(c[:4])}
               for c in seen_order]
    return entries, families


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    pdf = Path(sys.argv[1])
    if not pdf.exists():
        print(f"! not found: {pdf}", file=sys.stderr)
        return 1

    entries, families = parse(pdf)
    real = [e for e in entries if not e["residual"]]
    residual = [e for e in entries if e["residual"]]
    if len(real) < 2500:
        print(f"! only {len(real)} titles parsed — the PDF layout has changed or the wrong volume "
              f"was passed. Expected roughly 3,100.", file=sys.stderr)
        return 1

    OUT.write_text(json.dumps({
        "classification": "National Classification of Occupations (NCO) 2015",
        "authority": "Directorate General of Employment, Ministry of Labour & Employment, "
                     "Government of India",
        "source": SOURCE,
        "source_volume": "Volume I (Code Structure) — Concordance Table",
        "checked_on": __import__("datetime").date.today().isoformat(),
        "generated_by": "tools/nco_titles.py — do not hand-edit",
        "count_total": len(entries),
        "count_occupations": len(real),
        "count_residual": len(residual),
        "count_families": len(families),
        "note": "Extracted from the official PDF; the Ministry publishes no CSV or API. The "
                "published headline figure is 'about 3,600 occupations across 52 divisions'; this "
                "parse recovers the concordance rows, which is fewer, because titles broken across "
                "a page boundary by the PDF's text layer cannot be recovered reliably and are "
                "dropped rather than guessed at. That makes this list a FLOOR on NCO coverage: it "
                "can under-report a gap, never invent one. Codes ending .9900 are '…, Other' "
                "residual buckets and are flagged so the gap search can skip them.",
        "families": families,
        "titles": entries,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    kb = OUT.stat().st_size // 1024
    print(f"{OUT.relative_to(ROOT).as_posix()}  ({len(real)} occupations + {len(residual)} "
          f"residual buckets, {kb} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
