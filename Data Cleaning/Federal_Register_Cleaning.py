import json

with open("/home/dev/Masters_Thesis/Legal_Documents/title7_structure.json") as f:
    data = json.load(f)

def walk(node, depth=0):
    print("  " * depth, node.get("label"), node.get("citation"))
    if "content" in node:
        print("  " * (depth+1), node["content"][:120], "...")
    for child in node.get("children", []):
        walk(child, depth+1)

walk(data)
