import pdfplumber
import re
import json

pdf_path = "/home/dev/Masters_Thesis/Laws/fsman04a.pdf"
output_path = "/home/dev/Masters_Thesis/Laws/fsman04a_full_structured.json"

main_section_re = re.compile(r"(?:^|\n)(\d{2}-\d{3})\s+(.*?)\s+\1(?:\n|$)", re.IGNORECASE)
section_heading_re = re.compile(r"^\.(\d{1,3})\s+(.+)")
subsub_heading_re = re.compile(r"^\.(\d{1,3})(\d{1,3})\s+(.+)")
reference_re = re.compile(r"Section\s+(\d{2}-\d{3}\.\d+)", re.IGNORECASE)

def normalize_main_section(title, section_number):
    title = re.sub(r"\(Cont\.?\)|\(Continued\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    return f"{title.upper()} {section_number}"

def clean_text(text):
    text = re.sub(r"M\s+ANUAL", "MANUAL", text)
    text = re.sub(r"\bR\s+egulations\b", "Regulations", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

entries = []
current_main_section = ""
current_citation_prefix = ""
current_top_heading = None
current_top_subheading = None
current_entry = None
subheading_map = {}

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        lines = page.extract_text().split('\n')

        for line in lines:
            line = line.strip()

            if not line or "CALIFORNIA-DSS-MANUAL" in line or "FOOD STAMP REGULATIONS" in line:
                continue

            match_main = main_section_re.search(line)
            if match_main:
                current_citation_prefix = match_main.group(1)
                raw_title = match_main.group(2).strip()
                current_main_section = normalize_main_section(raw_title, current_citation_prefix)
                current_top_heading = None
                current_top_subheading = None
                continue

            match_top = section_heading_re.match(line)
            match_sub = subsub_heading_re.match(line)

            # Handle .x sections
            if match_top and not match_sub:
                if current_entry:
                    current_entry['text'] = clean_text(current_entry['text'])
                    current_entry['embedding_input'] = f"{current_entry['main_section']} : {current_entry['subsection']} {current_entry['text']}"
                    entries.append(current_entry)

                number = match_top.group(1)
                title = match_top.group(2).strip()
                current_top_heading = f"{current_citation_prefix}.{number}"
                current_top_subheading = title

                # Store subheading for inheritance by .1x, .2x, etc.
                subheading_map[current_top_heading] = title

                current_entry = {
                    "citation": f"MPP §{current_top_heading}",
                    "main_section": current_main_section,
                    "subsection": title,
                    "text": "",
                    "references": []
                }
                continue

            # Handle .xx or .xxx sections
            if match_sub:
                if current_entry:
                    current_entry['text'] = clean_text(current_entry['text'])
                    current_entry['embedding_input'] = f"{current_entry['main_section']} : {current_entry['subsection']} {current_entry['text']}"
                    entries.append(current_entry)

                parent_number = match_sub.group(1)
                sub_number = match_sub.group(2)
                full_number = f"{parent_number}{sub_number}"
                citation = f"MPP §{current_citation_prefix}.{full_number}"
                parent_key = f"{current_citation_prefix}.{parent_number}"
                inherited_subsection = subheading_map.get(parent_key, match_sub.group(3).strip())

                current_entry = {
                    "citation": citation,
                    "main_section": current_main_section,
                    "subsection": inherited_subsection,
                    "text": match_sub.group(3).strip(),
                    "references": []
                }
                continue

            # Accumulate text and detect references
            if current_entry:
                current_entry["text"] += " " + line

                refs = reference_re.findall(line)
                if refs:
                    current_entry.setdefault("references", []).extend(refs)

# Final entry
if current_entry:
    current_entry['text'] = clean_text(current_entry['text'])
    current_entry['embedding_input'] = f"{current_entry['main_section']} : {current_entry['subsection']} {current_entry['text']}"
    entries.append(current_entry)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(entries, f, indent=2, ensure_ascii=False)
