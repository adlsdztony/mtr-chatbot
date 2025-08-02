import sys, pathlib

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from database.scripts.strategy.markdown import MarkdownEmbedding

# 初始化
processor = MarkdownEmbedding(
    json_path=".data/result/manual/manual_content_list.json",
    markdown_path=".data/result/manual/manual.md",
)

# 执行处理
processor.run()
