import spacy
nlp = spacy.load("en_core_web_sm")

def extract_concepts(text):
    doc = nlp(text)
    concepts = []

    for chunk in doc.noun_chunks:
        words = [t.lemma_.lower() for t in chunk
                 if t.pos_ in ("NOUN", "ADJ", "PROPN")
                 and t.dep_ not in ("det", "punct")]
        if not words:
            continue

        # Split conjoined concepts
        current = []
        for w in words:
            if w in ("or", "and"):
                if current:
                    concepts.append(" ".join(current))
                    current = []
            else:
                current.append(w)
        if current:
            concepts.append(" ".join(current))

    # Structural filter: drop isolated nouns with no modifiers or dependents
    filtered = []
    for c in concepts:
        tokens = nlp(c)
        if len(tokens) > 1:
            filtered.append(c)
        elif len(tokens) == 1:
            t = tokens[0]
            if any(child.dep_ in ("amod", "compound", "nmod") for child in t.children):
                filtered.append(c)
            elif t.dep_ in ("amod", "compound", "nmod"):
                filtered.append(c)

    # Deduplicate while preserving order
    seen, ordered = set(), []
    for c in filtered:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered



# Example test
sentence = "A household must be living in the county in which it files an application for participation."
concepts = extract_concepts(sentence)
print(concepts)