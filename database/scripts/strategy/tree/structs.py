from dataclasses import dataclass
from typing_extensions import Optional, List


class SummarizationNode:
    content: str = ""
    title: str = ""
    summary: str = ""
    name: str = ""  # this name is also used to locate database
    keywords: List[str] = []
    children: List["SummarizationNode"] = []
    page: int = -1
    
    def __init__(self, name: str = "", title: str = ""):
        self.name = name
        self.title = title
        self.content = ""
        self.summary = ""
        self.keywords = []
        self.children = []
        self.page = -1


class DocumentTree:
    root: SummarizationNode
    
    def __init__(self, root: SummarizationNode):
        self.root = root
