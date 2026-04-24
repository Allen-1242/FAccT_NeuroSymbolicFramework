from sentence_transformers import SentenceTransformer
import json, re, torch, os

# ---------- CONFIG ----------
INPUT_FILE  = "/home/dev/Masters_Thesis/Laws/merged_mpp_attributes.json"
OUTPUT_FILE = "/home/dev/Masters_Thesis/Laws/mpp_section_sub_embeddings.json"
MODEL_NAME  = "BAAI/bge-base-en-v1.5"
BATCH_SIZE  = 32

# ---------- LOAD MODEL ----------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🚀 Loading model '{MODEL_NAME}' on {device} ...")
model = SentenceTransformer(MODEL_NAME, device=device)

# ---------- LOAD DATA ----------
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"📘 Loaded {len(data)} sections from {INPUT_FILE}")

# ---------- Helper: split text into subsections ----------
def split_subsections(text):
    """Split section text into roughly sentence-sized subsections."""
    if not text or len(text.strip()) < 20:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if len(s.split()) > 4]

# ---------- BATCH EMBEDDING ----------
def batch_encode(texts):
    """Encode in safe batches."""
    embs = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        batch_embs = model.encode(batch, normalize_embeddings=True, convert_to_numpy=True)
        embs.extend(batch_embs)
    return embs

# ---------- PROCESS SECTIONS ----------
total = len(data)
for idx, section in enumerate(data, start=1):
    text = section.get("text", "").strip()
    if not text:
        section["section_embedding_input"] = ""
        section["section_embedding"] = []
        section["subsections"] = []
        continue

    attr_names = [a.get("attribute", "") for a in section.get("attributes", []) if a.get("attribute")]
    phrase = f"{text} Attributes: {', '.join(attr_names)}"

    # --- Section embedding ---
    section["section_embedding_input"] = phrase
    section["section_embedding"] = model.encode([phrase], normalize_embeddings=True)[0].tolist()

    # --- Subsection embeddings ---
    subs = split_subsections(text)
    section["subsections"] = []
    if subs:
        sub_phrases = [f"Subsection {i}: {s}" for i, s in enumerate(subs, start=1)]
        sub_embs = batch_encode(sub_phrases)
        section["subsections"] = [
            {
                "subsection_id": f"{section.get('citation', 'Unknown')}-{i+1}",
                "text": subs[i],
                "embedding_input": sub_phrases[i],
                "embedding": sub_embs[i].tolist(),
            }
            for i in range(len(subs))
        ]

    if idx % 100 == 0 or idx == total:
        print(f"✅ Processed {idx}/{total} sections")

# ---------- SAVE ----------
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n🎯 Done. Generated embeddings for {total} sections and their subsections.")
print(f"💾 Saved to: {OUTPUT_FILE}")
