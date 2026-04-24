from docx import Document
import re
import json
import os

# ---------- INPUT / OUTPUT ----------
word_path = "/home/dev/Masters_Thesis/Laws/Manual_of_Policies_and_Procedures.docx"
output_path = "/home/dev/Masters_Thesis/Laws/mpp_full_structured.json"

# ---------- REGEX DEFINITIONS ----------
main_section_re_loose = re.compile(
    r"(?:MPP\s*)?(?P<num>\d{2}-\d{3})[\s\-:]+(?P<title>[A-Za-z].+)", re.IGNORECASE
)
section_heading_re = re.compile(r"^\.(\d{1,3})\s+(.+)")
subsub_heading_re = re.compile(r"^\.(\d{1,3})(\d{1,3})\s+(.+)")

# ---------- REFERENCE DETECTION ----------
reference_re = re.compile(
    r"(?:(?:Sec(?:tion)?s?\.?\s*)|(?:§\s*)|(?:Title\s*)|(?:CFR\s*)|(?:U\.S\.C\.))?"
    r"(?P<ref>(?:\d{2}-\d{3}(?:\.\d+)?(?:\([a-zA-Z0-9]+\))?)|"
    r"(?:\d+\s*CFR\s*\d+(?:\.\d+)?(?:\([a-zA-Z0-9]+\))?)|"
    r"(?:\d+\s*U\.?S\.?C\.?\s*\d+(?:\([a-zA-Z0-9]+\))?))",
    re.IGNORECASE
)

def extract_references(text):
    """Extract and normalize MPP, CFR, and USC references from a text line."""
    refs = []
    for m in reference_re.finditer(text):
        ref = m.group("ref").strip()

        # --- State (MPP) references ---
        if re.match(r"63-\d{3}", ref):
            ref = ref.replace(" ", "")
            refs.append({"type": "MPP", "ref": ref})
            continue

        # --- Federal CFR references ---
        if "CFR" in ref.upper():
            ref = re.sub(r"\s*CFR\s*", " CFR §", ref, flags=re.IGNORECASE)
            refs.append({"type": "CFR", "ref": ref})
            continue

        # --- Federal USC references ---
        if "USC" in ref.upper():
            ref = re.sub(r"\s*U\.?S\.?C\.?\s*", " U.S.C. §", ref, flags=re.IGNORECASE)
            refs.append({"type": "USC", "ref": ref})
            continue
    return refs

# ---------- CLEANING HELPERS ----------
def normalize_main_section(title, section_number):
    title = re.sub(r"\(Cont\.?\)|\(Continued\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    return f"{title.upper()} {section_number}"

def clean_text(text):
    text = re.sub(r"M\s+ANUAL", "MANUAL", text)
    text = re.sub(r"\bR\s+egulations\b", "Regulations", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ---------- PARSING ----------
doc = Document(word_path)
entries = []

current_main_section = ""
current_citation_prefix = ""
current_entry = None
subheading_map = {}
last_known_section = None

for para in doc.paragraphs:
    line = para.text.strip()
    if not line:
        continue
    if "CALIFORNIA-DSS-MANUAL" in line or "FOOD STAMP REGULATIONS" in line:
        continue

    # --- Detect main section header (63-xxx) ---
    match_main = main_section_re_loose.search(line)
    if match_main:
        current_citation_prefix = match_main.group("num")
        raw_title = match_main.group("title").strip()
        current_main_section = normalize_main_section(raw_title, current_citation_prefix)
        last_known_section = current_main_section
        current_entry = None
        continue

    # --- Fallback: inline section marker ---
    inline_main = re.search(r"63-\d{3}", line)
    if inline_main and not current_citation_prefix:
        current_citation_prefix = inline_main.group(0)
        current_main_section = f"AUTO-DETECTED SECTION {current_citation_prefix}"
        last_known_section = current_main_section

    match_top = section_heading_re.match(line)
    match_sub = subsub_heading_re.match(line)

    # --- Handle .1, .2, .3 subsections (with inline body and refs) ---
    if match_top and not match_sub:
        if current_entry:
            current_entry["text"] = clean_text(current_entry["text"])
            current_entry["embedding_input"] = (
                f"{current_entry['main_section']} : "
                f"{current_entry['subsection']} {current_entry['text']}"
            )
            entries.append(current_entry)

        number = match_top.group(1)
        rest = match_top.group(2).strip()

        # Split long inline lines: first ~10 tokens = title, rest = body
        parts = rest.split()
        if len(parts) > 10:
            title = " ".join(parts[:10])
            body = " ".join(parts[10:])
        else:
            title = rest
            body = ""

        current_top_heading = f"{current_citation_prefix}.{number}"
        subheading_map[current_top_heading] = title

        if not current_main_section:
            current_main_section = last_known_section or "UNSPECIFIED SECTION"

        current_entry = {
            "citation": f"MPP §{current_top_heading}",
            "main_section": current_main_section,
            "subsection": title,
            "text": clean_text(body),
            "references": extract_references(line),  # catch same-line refs
        }
        continue

    # --- Handle .11, .121 etc. ---
    if match_sub:
        if current_entry:
            current_entry["text"] = clean_text(current_entry["text"])
            current_entry["embedding_input"] = (
                f"{current_entry['main_section']} : "
                f"{current_entry['subsection']} {current_entry['text']}"
            )
            entries.append(current_entry)

        parent_number = match_sub.group(1)
        sub_number = match_sub.group(2)
        full_number = f"{parent_number}{sub_number}"
        citation = f"MPP §{current_citation_prefix}.{full_number}"
        parent_key = f"{current_citation_prefix}.{parent_number}"
        inherited_title = subheading_map.get(parent_key, match_sub.group(3).strip())

        if not current_main_section:
            current_main_section = last_known_section or "UNSPECIFIED SECTION"

        current_entry = {
            "citation": citation,
            "main_section": current_main_section,
            "subsection": inherited_title,
            "text": match_sub.group(3).strip(),
            "references": extract_references(line),
        }
        continue

    # --- Accumulate body text and detect references ---
    if current_entry:
        current_entry["text"] += " " + line
        for ref_obj in extract_references(line):
            current_entry.setdefault("references", []).append(ref_obj)

# --- Flush final entry ---
if current_entry:
    current_entry["text"] = clean_text(current_entry["text"])
    current_entry["embedding_input"] = (
        f"{current_entry['main_section']} : "
        f"{current_entry['subsection']} {current_entry['text']}"
    )
    entries.append(current_entry)

# ---------- POST-PROCESSING ----------
for e in entries:
    if not e["main_section"] or "INHERITED" in e["main_section"]:
        e["main_section"] = last_known_section or "UNSPECIFIED SECTION"

for e in entries:
    if e["main_section"].startswith("AUTO-DETECTED SECTION"):
        match = re.search(r"63-\d{3}", e["main_section"])
        if match:
            e["main_section"] = match.group(0)

# Deduplicate references
for e in entries:
    seen = set()
    cleaned_refs = []
    for r in e.get("references", []):
        key = f"{r['type']}:{r['ref']}"
        if key not in seen:
            seen.add(key)
            cleaned_refs.append(r)
    e["references"] = cleaned_refs

# ---------- SAVE ----------
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(entries, f, indent=2, ensure_ascii=False)

# ---------- SUMMARY ----------
total = len(entries)
orphans = sum(1 for e in entries if not e["main_section"] or "UNSPECIFIED" in e["main_section"])
auto = sum(1 for e in entries if "AUTO-DETECTED" in e["main_section"])
cfr_refs = sum(1 for e in entries for r in e.get("references", []) if r["type"] == "CFR")
usc_refs = sum(1 for e in entries for r in e.get("references", []) if r["type"] == "USC")
mpp_refs = sum(1 for e in entries for r in e.get("references", []) if r["type"] == "MPP")

print(f"✅ Extracted {total} sections to {output_path}")
print(f"⚙️  Cleaned orphan count: {orphans}")
print(f"🧭 Auto-detected remaining (should be 0): {auto}")
print(f"📘 References — MPP: {mpp_refs}, CFR: {cfr_refs}, USC: {usc_refs}")
if total > 0:
    print('🔹 Example:', entries[0])
