import json
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import pairwise_distances
import umap
import itertools
from scipy.spatial import ConvexHull
import matplotlib.patheffects as pe  

# -----------------------------
# 1. Load ontology JSON
# -----------------------------
with open("/home/dev/Masters_Thesis/Neuro_Symbolic/snap_ontology_with_embeddings_new.json", "r") as f:
    ontology = json.load(f)


ontology.pop("Agency", None)
ontology.pop("Residency", None)

point_names = []
point_embeddings = []
point_parent_group = []
parent_names = []

def add_parent_and_children(parent_name, parent_node):
    if "embedding" not in parent_node:
        return
    parent_names.append(parent_name)
    point_names.append(parent_name)
    point_embeddings.append(parent_node["embedding"])
    point_parent_group.append(parent_name)

    def walk_subtypes(subdict):
        for cname, cval in subdict.items():
            if isinstance(cval, dict):
                if "embedding" in cval:
                    point_names.append(cname)
                    point_embeddings.append(cval["embedding"])
                    point_parent_group.append(parent_name)
                if "subtypes" in cval:
                    walk_subtypes(cval["subtypes"])

    if "subtypes" in parent_node:
        walk_subtypes(parent_node["subtypes"])

for pname, pnode in ontology.items():
    if isinstance(pnode, dict) and "subtypes" in pnode:
        add_parent_and_children(pname, pnode)

embeddings = np.array(point_embeddings)
print(f"Total nodes (parents + subtypes): {len(point_names)}")
print(f"Parent concepts detected: {len(parent_names)}")

# -----------------------------
# 2. Cosine distances
# -----------------------------
cos_dist = pairwise_distances(embeddings, metric="cosine")
parent_indices = {name: i for i, name in enumerate(point_names) if name in parent_names}

# -----------------------------
# 3. Bubble sizes (semantic closeness)
# -----------------------------
base_size = 5
scale_factor = 2000
parent_size = 700

sizes = []
parent_children = {p: [] for p in parent_names}

for i, name in enumerate(point_names):
    if name in parent_names:
        sizes.append(parent_size)
    else:
        p_name = point_parent_group[i]
        p_idx = parent_indices[p_name]
        d = cos_dist[p_idx, i]
        sim = 1.0 - d
        size = base_size + (sim ** 2.5) * scale_factor
        sizes.append(size)
        parent_children[p_name].append((i, size))

# -----------------------------
# 4. Metrics: cluster coherence
# -----------------------------
pc_dists = []
for i, name in enumerate(point_names):
    if name in parent_names:
        continue
    p_name = point_parent_group[i]
    pc_dists.append(cos_dist[parent_indices[p_name], i])

pp_dists = []
pidx = list(parent_indices.values())
for i, j in itertools.combinations(pidx, 2):
    pp_dists.append(cos_dist[i,j])

pc_dists, pp_dists = np.array(pc_dists), np.array(pp_dists)
print(f"Mean parent–child cosine distance: {pc_dists.mean():.3f}")
print(f"Mean parent–parent cosine distance: {pp_dists.mean():.3f}")

# -----------------------------
# 5. UMAP projection
# -----------------------------
reducer = umap.UMAP(metric="cosine", n_neighbors=15, min_dist=0.05, random_state=42)
coords = reducer.fit_transform(embeddings)

# Select labels: largest + smallest subtype per parent
labels_to_annotate = set()
for p_name in parent_names:
    children = parent_children[p_name]
    if children:
        largest = max(children, key=lambda x: x[1])
        smallest = min(children, key=lambda x: x[1])
        labels_to_annotate.update([largest[0], smallest[0]])

# -----------------------------
# 6. Plot with convex hulls + legend
# -----------------------------
plt.figure(figsize=(13, 10))
cmap = plt.colormaps.get_cmap("tab10")
parent_to_color = {pname: cmap(i % 10) for i, pname in enumerate(parent_names)}

# Draw convex hull per parent group
for p_name in parent_names:
    idxs = [i for i, pg in enumerate(point_parent_group) if pg == p_name]
    if len(idxs) >= 3:
        pts = coords[idxs]
        hull = ConvexHull(pts)
        hull_pts = pts[hull.vertices]
        plt.fill(hull_pts[:,0], hull_pts[:,1], color=parent_to_color[p_name], alpha=0.15)

# Plot parent + subtype nodes
for i, (x, y) in enumerate(coords):
    name = point_names[i]
    color = parent_to_color[point_parent_group[i]]

    if name in parent_names:
        plt.scatter(x, y, s=sizes[i], color=color, edgecolor="black", linewidths=1.2, zorder=3)
        #plt.text(x+0.01, y+0.01, name, fontsize=11, weight="bold")

        # ...

        label_offset = 0.25  # bigger vertical offset

        # inside the plotting loop, for parents:
        if name in parent_names:
            plt.scatter(x, y, s=sizes[i], color=color,
                        edgecolor="black", linewidths=1.2, zorder=3)
            plt.text(
                x,
                y + label_offset,
                name,
                fontsize=11,
                weight="bold",
                ha="center",
                va="bottom",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8),
            )


    else:
        plt.scatter(x, y, s=sizes[i], color=color, alpha=0.75, zorder=2)
        if i in labels_to_annotate:
            plt.text(x+0.01, y+0.01, name, fontsize=8)

# Legend
for p_name in parent_names:
    plt.scatter([], [], s=100, color=parent_to_color[p_name], label=p_name)
plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))

plt.title("Ontology Parent–Subtype Embedding Structure with Convex Hulls")
plt.xlabel("UMAP-1")
plt.ylabel("UMAP-2")
plt.tight_layout()
plt.savefig("ontology_clusters_convex.png", dpi=300, bbox_inches="tight")
plt.show()

print("Saved: ontology_clusters_convex.png")