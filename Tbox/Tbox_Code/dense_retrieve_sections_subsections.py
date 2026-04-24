from sentence_transformers import SentenceTransformer, util
import numpy as np, json

# ---------- CONFIG ----------
MODEL_NAME = "BAAI/bge-base-en-v1.5"
DATA_FILE  = "/home/dev/Masters_Thesis/Laws/mpp_section_sub_embeddings.json"

SECTION_CUTOFF = 0.65       # section similarity threshold
SUBSECTION_CUTOFF = 0.55    # subsection similarity threshold

# ---------- LOAD ----------
print("Loading model and data...")
model = SentenceTransformer(MODEL_NAME)
with open(DATA_FILE) as f:
    data = json.load(f)
print(f"Loaded {len(data)} sections")

# ---------- QUERY ----------
query = input("Enter your explanation query:\n> ")
q_emb = model.encode(query, normalize_embeddings=True)

# ---------- STAGE 1: SECTION FILTER ----------If yo
valid_sections = []
for section in data:
    sec_emb = np.array(section["section_embedding"], dtype=np.float32)
    sec_score = util.cos_sim(q_emb, sec_emb).item()
    if sec_score >= SECTION_CUTOFF:
        valid_sections.append((sec_score, section))

# ---------- STAGE 2: SUBSECTION RETRIEVAL ----------
results = []
for sec_score, section in valid_sections:
    for sub in section.get("subsections", []):
        sub_emb = np.array(sub["embedding"], dtype=np.float32)
        sub_score = util.cos_sim(q_emb, sub_emb).item()
        if sub_score >= SUBSECTION_CUTOFF:
            results.append({
                "section_citation": section["citation"],
                "section_score": sec_score,
                "subsection_text": sub["text"],
                "subsection_score": sub_score,
                "attributes": [a["attribute"] for a in section.get("attributes", [])]
            })

# ---------- STAGE 3: OUTPUT ----------
if not results:
    print(f"\nNo subsections above cutoff ({SUBSECTION_CUTOFF}).")
else:
    results = sorted(results, key=lambda x: x["subsection_score"], reverse=True)
    print(f"\n🔍 Subsections above cutoff ({SUBSECTION_CUTOFF}): {len(results)}")
    for r in results:
        print(f"\n📘 Section: {r['section_citation']} (section_score={r['section_score']:.3f})")
        print(f"   ↳ Subsection_score={r['subsection_score']:.3f}")
        print("   Text:", r['subsection_text'][:200].strip(), "...")
        print("   Attributes:", ", ".join(r['attributes']))
