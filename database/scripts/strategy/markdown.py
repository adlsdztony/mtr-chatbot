import sys, pathlib
import chromadb
import json
import base64
from collections import defaultdict
from tqdm import tqdm
from typing import Union
from logging import getLogger

logger = getLogger(__name__)
sys.path.append(pathlib.Path(__file__).parents[2].as_posix())

from utils import functions, get_database, get_model, settings, metadata

TEXT_LENGTH_FILTER = 200


class MarkdownEmbedding:
    def __init__(self, json_path: str, markdown_path: str, filename: str = None):
        self.json_path = json_path
        self.markdown_path = markdown_path
        self.filename = filename or pathlib.Path(json_path).stem

        # Initialize base model using gemma3:27b
        self.base_model = get_model.get_base_model(use_model=settings.VISION_MODEL)

        # Initialize vector databases
        self.textdb = get_database.get_database("textdb")
        self.imgdb = get_database.get_database("imgdb")

        # Initialize text splitter
        self.text_splitter = get_database.get_text_splitter(
            chunk_size=1000, chunk_overlap=200
        )

        # Load JSON and markdown content
        with open(self.json_path, "r", encoding="utf-8") as f:
            self.json_data = json.load(f)

        with open(self.markdown_path, "r", encoding="utf-8") as f:
            self.markdown_content = f.read()

    def _get_context_around_text(self, text: str, context_length: int) -> str:
        """Get context around a specific text in markdown"""
        text_index = self.markdown_content.find(text)
        if text_index == -1:
            return text  # If text not found, return original text

        start_index = max(0, text_index - context_length)
        end_index = min(
            len(self.markdown_content), text_index + len(text) + context_length
        )

        return self.markdown_content[start_index:end_index]

    def _find_image_context(self, img_path: str, context_length: int) -> str:
        """Find context around image in markdown"""
        # Look for image reference pattern in markdown
        image_patterns = [
            f"![]({img_path})",
            f"![](images/{pathlib.Path(img_path).name})",
            pathlib.Path(img_path).name,
        ]

        for pattern in image_patterns:
            index = self.markdown_content.find(pattern)
            if index != -1:
                start = max(0, index - context_length)
                end = min(
                    len(self.markdown_content), index + len(pattern) + context_length
                )
                return self.markdown_content[start:end]

        return ""

    def _find_table_context(self, table_body: str, context_length: int) -> str:
        """Find context around table in markdown"""
        # Try to find table content or similar patterns
        if not table_body:
            return ""

        # Look for parts of table content in markdown
        table_text = table_body[:100]  # First 100 chars as search pattern
        index = self.markdown_content.find(table_text)

        if index != -1:
            start = max(0, index - context_length)
            end = min(
                len(self.markdown_content), index + len(table_text) + context_length
            )
            return self.markdown_content[start:end]

        return ""

    def _process_text_by_page(self, text_by_page):
        """Process text content grouped by page"""
        total_pages = len(text_by_page)

        for page_idx, text_items in tqdm(
            text_by_page.items(),
            desc="Processing text pages",
            unit="pages",
            total=total_pages,
        ):
            try:
                # Combine all text from the same page
                page_text = " ".join([item.get("text", "") for item in text_items])

                # Split text into chunks
                chunks = self.text_splitter.split_text(page_text)

                # Process chunks with nested progress bar
                chunk_desc = f"Page {page_idx} text chunks"
                for i, chunk in enumerate(
                    tqdm(chunks, desc=chunk_desc, unit="chunks", leave=False)
                ):
                    # Get context around this chunk
                    context = self._get_context_around_text(chunk, 500)

                    # Prepare metadata
                    metadata_dict = {
                        "page_idx": page_idx,
                        "summary": context,  # Include context as summary
                        "path": "",
                        "type": "text",
                        "filename": self.filename,
                    }

                    # Insert into textdb
                    self.textdb.add(
                        documents=[context],
                        metadatas=[metadata_dict],
                        ids=[f"text_{page_idx}_{i}"],
                    )

                tqdm.write(f"[OK] Processed page {page_idx}: {len(chunks)} text chunks")

            except Exception as e:
                tqdm.write(f"[ERROR] Failed to process text on page {page_idx}: {e}")
                logger.error(f"Error processing text on page {page_idx}: {e}")

    def _process_image(self, item):
        """Process image content"""
        img_path = item.get("img_path", "")
        page_idx = item.get("page_idx", 0)

        if not img_path:
            return

            # Encode image to base64
        full_img_path = pathlib.Path(self.json_path).parent / img_path

        # Get image context from markdown
        context = self._find_image_context(img_path, 500)

        # Generate summary with context
        summary = self._generate_summary_with_context(full_img_path, "image", context)

        # Prepare metadata
        metadata_dict = {
            "page_idx": page_idx,
            "summary": summary,
            "path": img_path,
            "type": "image",
            "filename": self.filename,
        }

        # Insert into imgdb
        self.imgdb.add(
            documents=[summary],
            metadatas=[metadata_dict],
            ids=[f"image_{page_idx}_{hash(img_path)}"],
        )

        tqdm.write(
            f"[OK] Processed image: {pathlib.Path(img_path).name} (Page: {page_idx})"
        )

    def _generate_summary_with_context(
        self,
        content_or_path: Union[str, pathlib.Path],
        content_type: str,
        context: str = "",
    ) -> str:
        # invoke LangChain model API to pass in images
        message = {
            "role": "user",
            "content": [
                functions.form_text(
                    "Based on the following markdown context and the image content, generate a detailed summary of what this image shows and its relevance to the document:"
                ),
                (
                    functions.form_image(content_or_path)
                    if isinstance(content_or_path, pathlib.Path)
                    else functions.form_text(content_or_path)
                ),
                functions.form_text(f"Context from Markdown: {context}"),
                functions.form_text(
                    "Please provide a concise summary that captures the key details and relevance of the image in the context of the document."
                ),
            ],
        }

        response = self.base_model.invoke([message])
        return response.text()

    def _process_table(self, item):
        """Process table content"""
        img_path = item.get("img_path", "")
        table_body = item.get("table_body", "")
        page_idx = item.get("page_idx", 0)

        try:
            if img_path:
                # Process as image if img_path is not empty
                context = (
                    self._find_table_context(table_body, 500)
                    if table_body
                    else self._find_image_context(img_path, 500)
                )
                full_img_path = pathlib.Path(self.json_path).parent / img_path
                summary = self._generate_summary_with_context(
                    full_img_path,
                    "table",
                    context,
                )
                path = img_path
                tqdm.write(
                    f"[OK] Processed table image: {pathlib.Path(img_path).name} (Page: {page_idx})"
                )
            else:
                # Process table body text
                context = self._find_table_context(table_body, 500)
                summary = self._generate_summary_with_context(
                    table_body, "table", context
                )
                path = ""
                tqdm.write(f"[OK] Processed table text (Page: {page_idx})")

            # Prepare metadata
            metadata_dict = {
                "page_idx": page_idx,
                "summary": summary,
                "path": path,
                "type": "table",
                "filename": self.filename,
            }

            # Insert into imgdb (as requested)
            self.imgdb.add(
                documents=[summary],
                metadatas=[metadata_dict],
                ids=[f"table_{page_idx}_{hash(str(item))}"],
            )

        except Exception as e:
            tqdm.write(f"[ERROR] Failed to process table (Page: {page_idx}): {e}")
            print(f"Error processing table on page {page_idx}: {e}")

    def run(self):
        """Process all content from JSON and embed into appropriate databases"""
        print("Start processing document...")

        # Count different types of content for progress tracking
        type_counts = defaultdict(int)
        for item in self.json_data:
            item_type = item.get("type", "unknown")
            type_counts[item_type] += 1

        print(
            f"Statistics: text: {type_counts['text']}, images: {type_counts['image']}, tables: {type_counts['table']}"
        )

        # Group text content by page_idx for later processing
        text_by_page = defaultdict(list)

        # NOTE - Collect text items by page
        text_items = [item for item in self.json_data if item.get("type") == "text"]
        for item in text_items:
            page_idx = item.get("page_idx", 0)
            text_by_page[page_idx].append(item)

        # Process text content grouped by page with progress bar
        if text_by_page:
            logger.info("Processing text content...")
            self._process_text_by_page(text_by_page)

        # NOTE - Process images and tables with progress bar
        non_text_items = [
            item for item in self.json_data if item.get("type") in ["image", "table"]
        ]

        if non_text_items:
            print("Processing images and tables...")
            for item in tqdm(
                non_text_items, desc="Processing images/tables", unit="items"
            ):
                item_type = item.get("type")
                assert item_type in [
                    "image",
                    "table",
                ], f"Unsupported item type: {item_type}"

                if item_type == "image":
                    self._process_image(item)
                elif item_type == "table":
                    self._process_table(item)

        logger.info("[OK] Document processing complete!")
