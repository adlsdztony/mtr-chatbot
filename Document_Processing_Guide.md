## Quick Start

Prepare your environment:

1. You need follow the instructions in the [README](./README.md) to set up the chatbot before going further.
2. Create venv and install dependencies with uv:
    - install uv (if not installed):
    
      on windows:
      ```bash
      powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
      ```
      on Linux/Mac/WSL:
      ```bash
      wget -qO- https://astral.sh/uv/install.sh | sh
      ```
    - make sure restart your terminal to have `uv` command available
    - then create venv and install dependencies:
      ```bash
      uv sync
      uv pip install -U "mineru[core]"
      ```

3. activate the venv in Linux/Mac:
    ```bash
    source .venv/bin/activate
    ```
    or on Windows cmd:
    ```bash
    .venv\Scripts\activate
    ```

4. pull required models:
    We assume you have ollama server running in docker.
    ```bash
    docker exec -it mtr-ollama ollama pull qwen2.5vl:7b # smaller version just for test
    docker exec -it mtr-ollama ollama pull bge-m3:latest
    ```

For a minimal processing workflow, you need to execute these operations in sequence:

1. **Prepare the document data**: 
    ```bash
    # Run mineru 
    mineru -p /path/to/pdf -o .data/result/
    ``` 
    It is normal longer time for the first run as it needs to download models.

2. **Run the embedding script**: 

   This will automatically process all documents in `.data/result/` and store results in ChromaDB in `database/storage/`
    ```bash
    python tests/run_multi_embedding.py
    ```
    The script will skip already processed files, so you can re-run it after adding new documents. To force re-processing of all files, use:
    ```bash
    python tests/run_multi_embedding.py --force
    ```

3. **Verify the outputs**: 

    You can check the processed text chunks using the chunk viewer:
    ```bash
    python chunk_viewer/run.py
    ```
    and check the results in your browser at `http://localhost:5000`

4. **Restart the chatbot**:
    
    After processing new documents, restart the chatbot service to load the updated database:
    ```bash
    docker compose restart chatbot
    ```

## Data Structure
The output from mineru is a set of JSON files and markdown files organized as follows:
```bash
.data/result/
├── document1/
│   ├── images/
│   │   ├── image1.png
│   ├── document1_content_list.json
│   └── document1.md
├── document2/
│   ├── images/
│   │   ├── image1.png
│   ├── document2_content_list.json
│   └── document2.md
└── ...
```
The data processing script will read these files, extract and chunk text, generate image descriptions, and create embeddings for storage in ChromaDB in `database/storage/`.
```bash
database/
└── storage/
    ├── ID1/
    ├── ID2/
    └── chroma.sqlite3
```
If you want to start fresh, simply delete the `database/storage/` directory and re-run the embedding script.

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

**Key Implementation**: The [`database/scripts/strategy/markdown.py (MarkdownEmbedding)`](database/scripts/strategy/markdown.py) class processes these files:
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
3. **Chunking**: The [`utils/get_database.py (text_splitter)`](utils/get_database.py) breaks text into overlapping segments
4. **Context Extraction**: For each chunk, the system extracts 500 characters of surrounding context from the original markdown

**Code Reference**: [`database/scripts/strategy/markdown.py (_process_text_by_page)`](database/scripts/strategy/markdown.py) method handles the chunking workflow.

### 3. Image Description Generation (qwen-vl)

**Purpose**: Generate detailed descriptions of images using the Qwen vision model for semantic search.

**Model Configuration**:
- **Vision Model**: `qwen2.5vl:7b` (configurable in [`utils/settings.py`](utils/settings.py))
- **Context Integration**: Combines image content with surrounding markdown text

**Process**:
1. **Image Loading**: Images are loaded from the specified path and encoded to base64
2. **Context Finding**: The system searches for image references in the markdown to extract surrounding context
3. **Description Generation**: The vision model analyzes the image along with contextual information
4. **Summary Creation**: Generates a detailed description capturing key visual elements and document relevance

**Implementation**: [`database/scripts/strategy/markdown.py (_process_image)`](database/scripts/strategy/markdown.py) and [`database/scripts/strategy/markdown.py (_generate_summary_with_context)`](database/scripts/strategy/markdown.py) methods.

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

**Configuration**: Embedding settings are managed in [`utils/get_database.py`](utils/get_database.py) via the `MultiModalEmbedding` class.