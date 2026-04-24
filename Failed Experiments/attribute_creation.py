from sentence_transformers import SentenceTransformer, util
import torch, re, json, os

# ---------- CONFIGURATION ----------
INPUT_FILE = "/home/dev/Masters_Thesis/Laws/mpp_full_structured.json"
OUTPUT_FILE = "/home/dev/Masters_Thesis/Laws/mpp_attributes_enriched.json"
BATCH_SIZE = 50  # for GPU memory safety
THRESHOLD = 0.55

# ---------- Load embedding model ----------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🚀 Using device: {device}")
model = SentenceTransformer("BAAI/bge-base-en-v1.5", device=device)

# ---------- Attribute categories ----------
ATTRIBUTES = [
    "Income", "Residency", "Benefits", "Citizenship", "Eligibility",
    "Disability", "Elderly", "Work Requirements", "Verification / Documentation",
    "SSN / Identification", "Household Composition", "Felony / Criminal Status",
    "Child", "Parental Control"
]
attr_embs = model.encode(ATTRIBUTES, normalize_embeddings=True, convert_to_tensor=True)

# ---------- Normative prototypes ----------
NORMATIVE_PROTOTYPES = {
    "Required": "This rule imposes an obligation or mandatory action.",
    "Prohibited": "This rule forbids or disallows an action.",
    "Defined": "This rule provides a definition or meaning of a term.",
    "Conditional": "This rule applies only under certain conditions or exceptions."
}
proto_labels = list(NORMATIVE_PROTOTYPES.keys())
proto_embs = model.encode(
    list(NORMATIVE_PROTOTYPES.values()),
    normalize_embeddings=True,
    convert_to_tensor=True
)

# ---------- Helper: windowed phrase ----------
def extract_phrase_window(text, keyword, window=10):
    words = text.split()
    for i, w in enumerate(words):
        if keyword.lower() in w.lower():
            start = max(0, i - window)
            end = min(len(words), i + window)
            return " ".join(words[start:end])
    return text

# ---------- Attribute detection ----------
def get_attributes(text, top_k=3):
    text_emb = model.encode([text], normalize_embeddings=True, convert_to_tensor=True)
    sims = util.cos_sim(text_emb, attr_embs)[0]
    ranked = []
    for i in sims.argsort(descending=True):
        score = float(sims[i])
        if score >= THRESHOLD:
            ranked.append({"attribute": ATTRIBUTES[i], "similarity": score})
        if len(ranked) >= top_k:
            break
    return ranked

# ---------- Normative type classifier ----------
def get_attribute_type_embedding(text):
    clause_emb = model.encode([text], normalize_embeddings=True, convert_to_tensor=True)
    sims = util.cos_sim(clause_emb, proto_embs)[0]
    idx = int(torch.argmax(sims))
    return proto_labels[idx], float(sims[idx])

# ---------- Combined clause classifier ----------
def classify_clause_attribute_specific(text):
    attributes = get_attributes(text)
    for a in attributes:
        phrase = extract_phrase_window(text, a["attribute"])
        label, conf = get_attribute_type_embedding(phrase)
        a["attribute_type"] = label
        a["confidence"] = conf
    return {"text": text, "attributes": attributes}

# ---------- Batched JSON classifier ----------
def classify_json(input_path=INPUT_FILE, output_path=OUTPUT_FILE):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    total = len(data)
    print(f"\n📘 Loaded {total} entries from {input_path}")

    # Process in GPU-safe batches
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = data[batch_start:batch_end]

        print(f"\n⚙️  Processing batch {batch_start+1}-{batch_end} of {total}")
        for i, item in enumerate(batch, start=batch_start + 1):
            text = item.get("text") or item.get("subsection") or item.get("embedding_input")
            if not text:
                continue

            citation = item.get("citation", f"item_{i}")
            print(f"   ↳ [{i}/{total}] {citation}")

            try:
                result = classify_clause_attribute_specific(text)
                result["citation"] = citation
                result["main_section"] = item.get("main_section", None)
                results.append(result)
            except Exception as e:
                print(f"⚠️  Error on item {i} ({citation}): {e}")
                continue

    # Save enriched file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Classification complete.")
    print(f"💾 Saved to: {output_path}")
    print(f"📊 Total processed: {len(results)} entries\n")
    return results

# ---------- MAIN ----------
if __name__ == "__main__":
    classify_json()
