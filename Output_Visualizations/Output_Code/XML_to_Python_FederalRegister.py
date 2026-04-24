from lxml import etree as ET
import json
import re
from bs4 import BeautifulSoup   

xml_file = "/home/dev/Masters_Thesis/Legal_Documents/title7.xml"
json_file = "/home/dev/Masters_Thesis/Legal_Documents/title7.json"

# Regex patterns
section_pattern = re.compile(r"(?:§+\s*\d+(?:\.\d+)*)")       
part_pattern = re.compile(r"[Pp]art\s+\d+")                  
subpart_pattern = re.compile(r"[Ss]ubpart\s+[A-Z]")          
usc_pattern = re.compile(r"\d+\s*U\.S\.C\.\s*[\w\.\-\(\)]+")  
marker_pattern = re.compile(r"^\(?[a-zA-Z0-9]+\)")

def clean_text(text):
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)

def clean_refs(refs):
    """Strip punctuation, whitespace, and duplicates"""
    cleaned = []
    for r in refs:
        r = r.strip().rstrip(".,;")
        if r and r not in cleaned:
            cleaned.append(r)
    return cleaned

def normalize_citation(citation: str) -> str:
    """Normalize citation string into a machine-friendly UID part"""
    if not citation:
        return "NA"
    # Replace § with S
    citation = citation.replace("§", "S")
    # Replace separators with underscores
    citation = re.sub(r"[^\w]+", "_", citation)
    # Collapse multiple underscores
    citation = re.sub(r"_+", "_", citation)
    return citation.strip("_")

def make_uid(node_type: str, citation: str) -> str:
    return f"{node_type}__{normalize_citation(citation)}"

def parse_paragraph(p, order, section_cite):
    """Extract marker, heading, and body from a paragraph <P> node"""
    full_text = "".join(p.itertext()).strip()

    marker = None
    heading = None
    body = full_text

    # --- Try to extract marker ---
    marker_match = marker_pattern.match(full_text)
    if marker_match:
        marker = marker_match.group()
        body = full_text[len(marker):].strip()

    # --- Check for italic heading (<I>) ---
    i_node = p.find("I")
    if i_node is not None and i_node.text:
        heading = i_node.text.strip()
        if heading and heading in body:
            body = body.replace(heading, "", 1).strip()

    citation = f"{section_cite} {marker}" if marker else section_cite

    return {
        "uid": make_uid("paragraph", citation),
        "citation": citation,
        "marker": marker,
        "heading": heading,
        "body": body,
        "order": order,
        "authority": section_cite,
        "node_type": "paragraph"
    }

entries = []
tree = ET.parse(xml_file)
root = tree.getroot()

# --- TITLES ---
for div in root.findall(".//DIV1[@TYPE='TITLE']"):
    title_num = div.attrib.get("N")
    head = clean_text(div.findtext("HEAD")) or ""
    citation = f"{title_num} CFR"
    entries.append({
        "uid": make_uid("title", citation),
        "citation": citation,
        "main_section": head,
        "subsection": "",
        "text": "",
        "references": {},
        "authority": None,  # root node
        "node_type": "title"
    })

# --- PARTS ---
for div in root.findall(".//DIV5[@TYPE='PART']"):
    part_num = div.attrib.get("N")
    head = clean_text(div.findtext("HEAD")) or ""

    # Find parent Title
    parent_title = None
    for ancestor in div.iterancestors():
        if ancestor.tag == "DIV1" and ancestor.attrib.get("TYPE") == "TITLE":
            parent_title = ancestor.attrib.get("N")
            break

    citation = f"7 CFR Part {part_num}"

    entries.append({
        "uid": make_uid("part", citation),
        "citation": citation,
        "main_section": head,
        "subsection": "",
        "text": "",
        "authority": f"{parent_title} CFR" if parent_title else None,
        "references": {},
        "node_type": "part"
    })

# --- SUBPARTS ---
for div in root.findall(".//DIV6[@TYPE='SUBPART']"):
    subpart = div.attrib.get("N")
    head = clean_text(div.findtext("HEAD")) or ""

    parent_part = None
    for ancestor in div.iterancestors():
        if ancestor.tag == "DIV5" and ancestor.attrib.get("TYPE") == "PART":
            parent_part = ancestor.attrib.get("N")
            break

    citation = f"7 CFR Part {parent_part} Subpart {subpart}" if parent_part else f"7 CFR Subpart {subpart}"

    entries.append({
        "uid": make_uid("subpart", citation),
        "citation": citation,
        "main_section": head,
        "subsection": "",
        "text": "",
        "authority": f"7 CFR Part {parent_part}" if parent_part else None,
        "references": {},
        "node_type": "subpart"
    })

# --- SECTIONS ---
for div in root.findall(".//DIV8[@TYPE='SECTION']"):
    head = clean_text(div.findtext("HEAD")) or ""
    sectno = ""
    subject = ""

    if head.startswith("§"):
        parts = head.split(" ", 2)
        if len(parts) >= 2:
            sectno = f"§ {parts[1]}"
        if len(parts) == 3:
            subject = parts[2]

    section_cite = f"7 CFR {sectno}" if sectno else ""

    # Collect paragraph nodes
    paragraphs = []
    for i, p in enumerate(div.findall("P"), start=1):
        paragraphs.append(parse_paragraph(p, i, section_cite))

    # --- Find parent PART number ---
    parent_part = None
    for ancestor in div.iterancestors():
        if ancestor.tag == "DIV5" and ancestor.attrib.get("TYPE") == "PART":
            parent_part = ancestor.attrib.get("N")
            break

    # Extract refs
    text = " ".join(p["body"] for p in paragraphs)
    raw_sections = section_pattern.findall(text)
    raw_parts = part_pattern.findall(text)
    raw_subparts = subpart_pattern.findall(text)
    raw_usc = usc_pattern.findall(text)

    refs = {
        "sections": clean_refs(raw_sections),
        "parts": clean_refs([f"7 CFR Part {p.split()[1]}" for p in raw_parts]),
        "subparts": clean_refs([f"7 CFR Part {parent_part} {s}" for s in raw_subparts]) if parent_part else [],
        "usc": clean_refs(raw_usc)
    }

    entries.append({
        "uid": make_uid("section", section_cite),
        "citation": section_cite,
        "main_section": "Title 7 - Agriculture",
        "subsection": subject,
        "paragraphs": paragraphs,
        "authority": f"7 CFR Part {parent_part}" if parent_part else None,
        "references": refs,
        "node_type": "section"
    })

# --- Write JSON ---
with open(json_file, "w", encoding="utf-8") as f:
    json.dump(entries, f, indent=2, ensure_ascii=False)

print(f"Extracted {len(entries)} entries (Titles, Parts, Subparts, Sections, Paragraphs) from {xml_file} → {json_file}")
