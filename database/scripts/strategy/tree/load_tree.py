import xml.etree.ElementTree as ET
import pathlib, sys, json, pickle

sys.path.append(pathlib.Path(__file__).parents[4].as_posix())

from structs import SummarizationNode, DocumentTree
from utils import get_model, settings
from typing_extensions import Union, List, Optional, Dict
from collections import defaultdict


summarizer = get_model.get_base_model(settings.VISION_MODEL)


def title_tree(md: List[str]) -> DocumentTree:
    """H1 -> [H2] -> [[H3]] -> ...."""
    root = SummarizationNode(name="root", title="")
    queue: List[SummarizationNode] = [root]

    for line in md:
        line = line.strip()
        if not line.startswith("#"):
            queue[-1].content += line + "\n"
            continue

        level = line.count("#")
        node = SummarizationNode(title=line)
        while queue and level <= queue[-1].title.count("#"):
            queue.pop()

        queue[-1].children.append(node)
        print(f"Adding node: {node.title[:10]} to parent: {queue[-1].title[:10]}")
        queue.append(node)

    return DocumentTree(root=root)


# NOTE - inject page number and name
def dfs(node: SummarizationNode, data):
    # NOTE - inject page
    if node.title:
        for item in data:
            if item["text"][:10] == node.title[:10]:
                node.page = item["page_idx"]
                break
            
    # NOTE - summarize

    for child in node.children:
        dfs(child, data)


def load_data(mdpath: Union[str, pathlib.Path], jsonpath: Union[str, pathlib.Path]):
    with open(mdpath, "r", encoding="utf-8") as file:
        content = file.readlines()
    with open(jsonpath, "r", encoding="utf-8") as file:
        data = json.load(file)

    # NOTE - Use Queueing methods to build tree
    tree = title_tree(content)

    dfs(tree.root, data)
    return tree


if __name__ == "__main__":
    tree = load_data(
        ".data/result/manual/manual_adjusted_headings.md",
        ".data/result/manual/manual_content_list.json",
    )

    with open("database/storage/tree.pkl", "wb") as file:
        pickle.dump(tree, file)
