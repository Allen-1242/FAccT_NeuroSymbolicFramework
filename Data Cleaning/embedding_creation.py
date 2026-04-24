# make_embedding_corpora.py
import json, lzma, re, unicodedata
from collections import defaultdict

INPUT  = "uscode_stitched.jsonl.xz"      # from the stitcher
OUT_SUBSECS = "uscode_subsections.jsonl.xz"  # high-precision
OUT_SECTIONS = "uscode_sections.jsonl.xz"    # backstop/recall

# ---- helpers (keep in sync with stitcher) ----
def norm(s: str) -> str:
    if not s: return ""
    SMARTS = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u00A0": " ",
    }
    s = unicodedata.normalize("NFC", s)
    for k, v in SMARTS.items(): s = s.replace(k, v)
    return s

PAREN_LOWER = re.compile(r"^\([a-z]\)$")
PAREN_NUM   = re.compile(r"^\(\d+\)$")
PAREN_UPPER = re.compile(r"^\([A-Z]\)$")
PAREN_ROMAN = re.compile(r"^\([ivxlcdm]+\)$", re.IGNORECASE)

def sort_key_for_subkey(subkey: str):
    # "" (root) sorts first
    if not subkey: return ((0, -1),)
    toks = re.findall(r"\([^\)]+\)", subkey)
    key = []
    for t in toks:
        if PAREN_LOWER.match(t): key.append((1, ord(t[1]) - 97))
        elif PAREN_NUM.match(t): key.append((2, int(t[1:-1])))
        elif PAREN_UPPER.match(t): key.append((3, ord(t[1]) - 65))
        elif PAREN_ROMAN.match(t): key.append((4, (len(t), t.lower())))
        else: key.append((9, t))
    return tuple(key)

def make_id(title: str, section: str, subsection: str):
    ssub = subsection if subsection else "root"
    # strip "§" to keep IDs filename/URL-friendly
    sec = section.replace("§", "")
    return f"title{title}_sec{sec}_{ssub}".replace(" ", "")

# ---- load stitched → group by (title, section) ----
groups = defaultdict(list)
with lzma.open(INPUT, "rt", encoding="utf-8") as fin:
    for ln in fin:
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        title = str(rec.get("title", "")).strip()
        section = str(rec.get("section", "")).strip()
        subsection = rec.get("subsection", "")
        text = norm(rec.get("text", "")).strip()
        if not section or not text:
            continue
        groups[(title, section)].append((subsection, text))

# ---- write high-precision (one vector per subsection) ----
sub_rows = 0
with lzma.open(OUT_SUBSECS, "wt", encoding="utf-8", preset=6) as fout:
    for (title, section), items in groups.items():
        items.sort(key=lambda it: sort_key_for_subkey(it[0]))
        for subsection, text in items:
            # Breadcrumb context in the text header helps embeddings
            breadcrumb = f"Title {title} {section} {subsection}".strip()
            doc = {
                "id": make_id(title, section, subsection),
                "title": title,
                "section": section,
                "subsection": subsection,  # "" means root/preamble
                "text": f"{breadcrumb}\n\n{text}".strip()
            }
            fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
            sub_rows += 1

# ---- write backstop/recall (one vector per whole section) ----
sec_rows = 0
with lzma.open(OUT_SECTIONS, "wt", encoding="utf-8", preset=6) as fout:
    for (title, section), items in groups.items():
        items.sort(key=lambda it: sort_key_for_subkey(it[0]))
        # Concatenate in hierarchical order. Add tiny labels so structure survives.
        chunks = []
        for subsection, text in items:
            label = subsection if subsection else ""
            if label:
                chunks.append(f"{label}\n{text}".strip())
            else:
                chunks.append(text.strip())
        full_text = ("\n\n").join([c for c in chunks if c]).strip()
        if not full_text:
            continue
        doc = {
            "id": make_id(title, section, ""),
            "title": title,
            "section": section,
            "subsection": "",               # whole-section aggregate
            "text": f"Title {title} {section}\n\n{full_text}"
        }
        fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
        sec_rows += 1

print(f"[SUBSECS] wrote {sub_rows} → {OUT_SUBSECS}")
print(f"[SECTIONS] wrote {sec_rows} → {OUT_SECTIONS}")
