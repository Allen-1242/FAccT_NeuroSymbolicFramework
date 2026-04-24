import json
from collections import defaultdict

# ---------- CONFIG ----------
LEGAL_FILE = "legal_structure.json"
ATTR_FILE  = "attributes.json"
OUTPUT_FILE = "merged_legal_expressions.json"

# ---------- LOAD FILES ----------
with open(LEGAL_FILE, "r") as f:
    legal_data = json.load(f)

with open(ATTR_FILE, "r") as f:
    attr_data = json.load(f)

print(f"Loaded {len(legal_data)} legal nodes and {len(attr_data)} attribute entries.")

# ---------- BUILD ATTRIBUTE DICT ----------
# Keyed by citation (or change to subsection if that’s your Neo4j key)
attr_dict = defaultdict(dict)
for a in attr_data:
    key = a.get("citation") or a.get("main_section")
    if not key:
        continue
    attr_dict[key] = {
        "text": a.get("text", ""),
        "attributes": a.get("attributes", []),
        "main_section": a.get("main_section", "")
    }

# ---------- MERGE ----------
merged = []
missing_attrs = 0
for node in legal_data:
    citation = node.get("citation") or node.get("main_section")
    merged_node = dict(node)  # copy to avoid mutating original
    
    if citation and citation in attr_dict:
        info = attr_dict[citation]
        merged_node["text"] = info["text"]
        merged_node["attributes"] = info["attributes"]
        merged_node["main_section"] = info["main_section"]
        
        # Flatten attribute names for embedding input
        attr_names = [a["attribute"] for a in info["attributes"]]
        merged_node["embedding_input"] = f'{info["text"]} | ' + " | ".join(attr_names)
    else:
        missing_attrs += 1
        merged_node["attributes"] = []
        merged_node["embedding_input"] = merged_node.get("text", "")
    
    merged.append(merged_node)

print(f"Merged {len(merged)} nodes — {len(attr_dict)} had attributes, {missing_attrs} missing attributes.")

# ---------- SAVE ----------
with open(OUTPUT_FILE, "w") as f:
    json.dump(merged, f, indent=2)

print(f"Merged file saved to: {OUTPUT_FILE}")
