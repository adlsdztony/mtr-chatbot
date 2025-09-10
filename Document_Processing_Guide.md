## Quick Start

Prepare your environment:
1. Create venv and install dependencies with uv:
    ```bash
    uv sync
    uv pip install -U "mineru[core]"
    ```
    or manually:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install -U "mineru[core]"
    ```

2. activate the venv in Linux/Mac:
    ```bash
    source .venv/bin/activate
    ```
    or on Windows:
    ```bash
    .venv\Scripts\activate
    ```

3. pull required models:
    ```bash
    docker exec -it mtr-ollama ollama pull qwen2.5vl:7b # smaller version just for test
    docker exec -it mtr-ollama ollama pull bge-m3:latest
    ```

For a minimal processing workflow, you need to execute these operations in sequence:

1. **Prepare the document data**: Run mineru `mineru -p /path/to/pdf -o .data/result/` directory
2. **Run the embedding script**: Execute `python tests/run_embedding.py`
3. **Verify the outputs**: Run `python chunk_viewer/run.py` and check the results in your browser at `http://localhost:5000`

## System Requirements

- **Python Environment**: Python 3.8+
- **Required Models**: 
  - Vision Model: `qwen2.5vl:7b` (for image description)
  - Embedding Model: `bge-m3:latest` (for text/image embeddings)
- **Data Format**: JSON metadata + Markdown content files
- **Storage**: ChromaDB vector database

## Detailed Processing Workflow

### 1. Layout Detection & Text/Image Extraction

**Purpose**: Extract structured content from documents and organize it by type and page location with mineru.

```bash
mineru -p /path/to/pdf -o .data/result/
```

**JSON Structure Output**:
```json
[
  {
    "type": "text",
    "text": "Your text content here",
    "page_idx": 1
  },
  {
    "type": "image", 
    "img_path": "images/diagram1.png",
    "page_idx": 2
  },
  {
    "type": "table",
    "table_body": "Table content or empty if image-based",
    "img_path": "images/table1.png",
    "page_idx": 3
  }
]
```

**Key Implementation**: The [`MarkdownEmbedding`](database/scripts/strategy/markdown.py) class processes these files:
- Loads JSON metadata and markdown content
- Groups content by type (text, image, table) and page number
- Maintains page-level organization for context preservation

### 2. Text Chunking

**Purpose**: Split long text content into manageable chunks while preserving semantic coherence.

**Configuration**:
- **Chunk Size**: 1000 characters per chunk
- **Overlap**: 200 characters between adjacent chunks  
- **Splitter**: `RecursiveCharacterTextSplitter` from LangChain

**Process**:
1. **Page Grouping**: Text items are grouped by `page_idx`
2. **Text Combination**: All text from the same page is concatenated
3. **Chunking**: The [`text_splitter`](utils/get_database.py) breaks text into overlapping segments
4. **Context Extraction**: For each chunk, the system extracts 500 characters of surrounding context from the original markdown

**Code Reference**: [`_process_text_by_page`](database/scripts/strategy/markdown.py) method handles the chunking workflow.

### 3. Image Description Generation (qwen-vl)

**Purpose**: Generate detailed descriptions of images using the Qwen vision model for semantic search.

**Model Configuration**:
- **Vision Model**: `qwen2.5vl:7b` (configurable in [`settings.py`](utils/settings.py))
- **Context Integration**: Combines image content with surrounding markdown text

**Process**:
1. **Image Loading**: Images are loaded from the specified path and encoded to base64
2. **Context Finding**: The system searches for image references in the markdown to extract surrounding context
3. **Description Generation**: The vision model analyzes the image along with contextual information
4. **Summary Creation**: Generates a detailed description capturing key visual elements and document relevance

**Implementation**: [`_process_image`](database/scripts/strategy/markdown.py) and [`_generate_summary_with_context`](database/scripts/strategy/markdown.py) methods.

### 4. Output Checking

**Output Location**: Text chunks are stored in the `textdb` ChromaDB collection.

**Check with GUI:**
You can view and verify text chunks by running the chunk viewer:
```bash
python chunk_viewer/run.py
```
You can then access the viewer at `http://localhost:5000` in your web browser.


### 5. Embedding: Text and Image (Caption + Description)

**Purpose**: Convert text chunks and image descriptions into vector embeddings for semantic search.

**Embedding Model**: `bge-m3:latest` - a multilingual embedding model that handles both text and image descriptions.

**Process**:
1. **Text Embedding**: Each text chunk (with context) is converted to a vector representation
2. **Image Embedding**: Image descriptions are embedded using the same model for unified search
3. **Storage**: Vectors are stored in ChromaDB with associated metadata for retrieval

**Configuration**: Embedding settings are managed in [`get_database.py`](utils/get_database.py) via the `MultiModalEmbedding` class.