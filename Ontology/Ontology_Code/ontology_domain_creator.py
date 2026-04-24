"""
ontology_embedder_update.py
---------------------------
Embeds each ontology node using only its definition text.
Adds 'embedding' vectors to each node and saves updated JSON.
"""

import json
from sentence_transformers import SentenceTransformer
from pathlib import Path


class OntologyEmbedderUpdater:
    def __init__(self, model_name: str = "intfloat/e5-large-v2"):
        """Initialize the embedding model."""
        self.model = SentenceTransformer(model_name)

    def _update_embeddings_recursive(self, node, prefix=""):
        """Recursively embed each ontology node and its subtypes."""
        label = prefix if prefix else "Root"
        definition = node.get("definition", "")

        # Avoid overly repetitive label chains: use only last segment of label
        short_label = label.split(".")[-1]
        text_to_embed = f"{short_label}: {definition}".strip()

        # Generate embedding once
        embedding = self.model.encode(text_to_embed, normalize_embeddings=True).tolist()
        node["embedding"] = embedding

        # Recurse into subtypes if they exist
        if "subtypes" in node and isinstance(node["subtypes"], dict):
            for subkey, subnode in node["subtypes"].items():
                sub_label = f"{label}.{subkey}" if label != "Root" else subkey
                self._update_embeddings_recursive(subnode, prefix=sub_label)

    def embed_and_update(self, ontology_path: str, output_path: str = None):
        """Load ontology JSON, embed all nodes, and save updated version."""
        ontology = json.loads(Path(ontology_path).read_text())

        for root_key, root_node in ontology.items():
            self._update_embeddings_recursive(root_node, prefix=root_key)

        target_path = output_path or ontology_path
        Path(target_path).write_text(json.dumps(ontology, indent=2))
        print(f"Ontology updated with definition-only embeddings at {target_path}")

        # Diagnostic info
        sample_key = next(iter(ontology))
        dim = len(ontology[sample_key]["embedding"])
        print(f"Model: {self.model._first_module().auto_model.config._name_or_path}")
        print(f"Embedding dimension: {dim}")

        return ontology


# ---------- Example usage ----------
if __name__ == "__main__":
    input_file = "snap_domain.json"
    output_file = "snap_ontology_with_embeddings_new.json"

    updater = OntologyEmbedderUpdater()
    updated_ontology = updater.embed_and_update(input_file, output_path=output_file)