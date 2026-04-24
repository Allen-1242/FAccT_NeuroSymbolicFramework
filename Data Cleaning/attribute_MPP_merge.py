import json
import os
from collections import defaultdict

# ---------- CONFIG ----------
MPP_FILE = "/home/dev/Masters_Thesis/Laws/mpp_full_structured.json"      # base parsed MPP file
ATTR_FILE = "/home/dev/Masters_Thesis/Laws/mpp_attributes_enriched.json"      # classified attributes
OUTPUT_FILE = "/home/dev/Masters_Thesis/Laws/merged_mpp_attributes.json"

# ---------- LOAD ----------
with open(MPP_FILE, "r", encoding="utf-8") as f:
    mpp_data = json.load(f)

with open(ATTR_FILE, "r", encoding="utf-8") as f:
    attr_data = json.load(f)

print(f"📘 Loaded {len(mpp_data)} MPP nodes and {len(attr_data)} attribute entries.")

# ---------- HELPER: Normalize citation ----------
def normalize_citation(cite: str) -> str:
    """Strip MPP § and whitespace for consistent joins."""
    if not cite:
        return ""
    cite = cite.replace("MPP", "").replace("§", "").strip()
    return cite

# ---------- BUILD ATTRIBUTE LOOKUP ----------
attr_dict = defaultdict(dict)
for a in attr_data:
    key = normalize_citation(a.get("citation")) or a.get("main_section")
    if not key:
        continue
    attr_dict[key] = {
        "text": a.get("text", ""),
        "attributes": a.get("attributes", []),
        "main_section": a.get("main_section", "")
    }

# ---------- MERGE ----------
merged = []
attached, missing = 0, 0

for node in mpp_data:
    citation = normalize_citation(node.get("citation")) or node.get("main_section")
    merged_node = dict(node)  # avoid mutating original

    if citation and citation in attr_dict:
        info = attr_dict[citation]
        merged_node["attributes"] = info.get("attributes", [])
        merged_node["text"] = info.get("text", node.get("text", ""))
        merged_node["main_section"] = info.get("main_section", node.get("main_section", ""))

        # Build embedding input = text + attribute names
        attr_names = [a["attribute"] for a in info.get("attributes", [])]
        merged_node["embedding_input"] = f"{merged_node['text']} | " + " | ".join(attr_names)
        attached += 1
    else:
        merged_node["attributes"] = []
        merged_node["embedding_input"] = merged_node.get("text", "")
        missing += 1

    merged.append(merged_node)

print(f"✅ Successfully merged {attached} nodes with attributes.")
print(f"⚠️  {missing} nodes had no attribute match.")

# ---------- SAVE ----------
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)

print(f"💾 Saved merged data → {OUTPUT_FILE}")
