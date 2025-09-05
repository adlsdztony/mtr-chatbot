# Document Processing Guide

This guide provides step-by-step instructions for processing documents using the MTR Chatbot system. The pipeline transforms raw documents into a searchable knowledge base through layout detection, text extraction, image description generation, and vector embedding.

## Quick Start

For a minimal processing workflow, you need to execute these operations in sequence:

1. **Prepare your document data**: Place your JSON metadata file and Markdown content file in the `.data/result/manual/` directory
2. **Run the embedding script**: Execute `python tests/run_embedding.py`
3. **Verify the outputs**: Check the ChromaDB storage and generated summaries

```bash
# Quick execution - assumes data files are already prepared
cd /path/to/mtr-chatbot
python tests/run_embedding.py
```

## System Requirements

- **Python Environment**: Python 3.8+
- **Required Models**: 
  - Vision Model: `qwen2.5vl:72b` (for image description)
  - Embedding Model: `bge-m3:latest` (for text/image embeddings)
- **Data Format**: JSON metadata + Markdown content files
- **Storage**: ChromaDB vector database

## Detailed Processing Workflow

### 1. Layout Detection & Text/Image Extraction

**Purpose**: Extract structured content from documents and organize it by type and page location.

**Input Requirements**:
- JSON metadata file: `manual_content_list.json` containing structured document elements
- Markdown content file: `manual.md` containing the raw document text

**JSON Structure Expected**:
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
- **Vision Model**: `qwen2.5vl:72b` (configurable in [`settings.py`](utils/settings.py))
- **Context Integration**: Combines image content with surrounding markdown text

**Process**:
1. **Image Loading**: Images are loaded from the specified path and encoded to base64
2. **Context Finding**: The system searches for image references in the markdown to extract surrounding context
3. **Description Generation**: The vision model analyzes the image along with contextual information
4. **Summary Creation**: Generates a detailed description capturing key visual elements and document relevance

**Implementation**: [`_process_image`](database/scripts/strategy/markdown.py) and [`_generate_summary_with_context`](database/scripts/strategy/markdown.py) methods.

### 4. Output Checking and Manual Modification

**This section is crucial for quality control and customization.**

#### 4.1 Checking Text Chunks

**Output Location**: Text chunks are stored in the `textdb` ChromaDB collection.

**Verification Methods**:

1. **Database Inspection**:
```python
# Access the text database
from utils.get_database import get_database
textdb = get_database("textdb")

# Check total count
print(f"Total text chunks: {textdb.count()}")

# Sample some entries
results = textdb.peek(limit=5)
for i, (doc, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
    print(f"Chunk {i+1}:")
    print(f"  Page: {metadata['page_idx']}")
    print(f"  Content: {doc[:100]}...")
    print(f"  Type: {metadata['type']}")
    print()
```

2. **Manual Review Process**:
   - **Check chunk boundaries**: Ensure chunks don't break mid-sentence or mid-concept
   - **Verify context accuracy**: Confirm that the extracted context properly represents the chunk's position
   - **Assess completeness**: Check that no critical information is lost during chunking

**Modification Options**:

1. **Adjust Chunking Parameters**: Modify chunk size and overlap in [`get_database.py`](utils/get_database.py):
```python
def get_text_splitter(chunk_size: int = 1000, chunk_overlap: int = 200):
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,  # Increase for longer chunks
        chunk_overlap=chunk_overlap,  # Adjust overlap as needed
        length_function=len,
    )
```

2. **Custom Text Filtering**: Modify the `TEXT_LENGTH_FILTER` in [`markdown.py`](database/scripts/strategy/markdown.py) to exclude short text segments.

3. **Manual Content Editing**: Edit the source markdown file before processing to improve chunk quality.

#### 4.2 Checking Image Descriptions

**Output Location**: Image descriptions are stored in the `imgdb` ChromaDB collection.

**Verification Methods**:

1. **Database Inspection**:
```python
# Access the image database  
from utils.get_database import get_database
imgdb = get_database("imgdb")

# Check image descriptions
results = imgdb.peek(limit=5)
for i, (description, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
    print(f"Image {i+1}:")
    print(f"  Path: {metadata['path']}")
    print(f"  Page: {metadata['page_idx']}")
    print(f"  Description: {description}")
    print(f"  Type: {metadata['type']}")
    print()
```

2. **Quality Assessment Checklist**:
   - **Visual Accuracy**: Does the description accurately capture what's shown in the image?
   - **Context Relevance**: Does it relate properly to the surrounding document content?
   - **Detail Level**: Is the description detailed enough for search but not overly verbose?
   - **Technical Terminology**: Are technical terms correctly identified and described?

**Modification Strategies**:

1. **Prompt Engineering**: Modify the vision model prompt in [`_generate_summary_with_context`](database/scripts/strategy/markdown.py):
```python
# Current prompt
"Based on the following markdown context and the image content, generate a detailed summary..."

# Customize for your domain:
"As a technical documentation expert, analyze this image in the context of [YOUR_DOMAIN]. Focus on [SPECIFIC_ASPECTS] and provide a description that emphasizes [KEY_ELEMENTS]..."
```

2. **Context Window Adjustment**: Modify the context length (currently 500 characters) in [`_find_image_context`](database/scripts/strategy/markdown.py) to provide more or less surrounding text.

3. **Manual Description Override**: For critical images, manually edit descriptions in the database:
```python
# Update specific image description
imgdb.update(
    ids=["image_2_12345"],  # Use the actual ID
    documents=["Your improved description here"],
    metadatas=[{
        "page_idx": 2,
        "summary": "Your improved description here", 
        "path": "images/critical_diagram.png",
        "type": "image"
    }]
)
```

#### 4.3 Table Processing Verification

Tables can be processed either as images (if `img_path` is provided) or as text content:

**For Image-based Tables**:
- Follow the same verification process as images above
- Pay special attention to data accuracy in the generated descriptions

**For Text-based Tables**:
- Check that table structure is preserved in the description
- Verify that relationships between data points are clearly explained

### 5. Embedding: Text and Image (Caption + Description)

**Purpose**: Convert text chunks and image descriptions into vector embeddings for semantic search.

**Embedding Model**: `bge-m3:latest` - a multilingual embedding model that handles both text and image descriptions.

**Process**:
1. **Text Embedding**: Each text chunk (with context) is converted to a vector representation
2. **Image Embedding**: Image descriptions are embedded using the same model for unified search
3. **Storage**: Vectors are stored in ChromaDB with associated metadata for retrieval

**Configuration**: Embedding settings are managed in [`get_database.py`](utils/get_database.py) via the `MultiModalEmbedding` class.

**Verification**:
```python
# Check embedding dimensions and storage
from utils.get_database import get_database

textdb = get_database("textdb")
imgdb = get_database("imgdb")

print(f"Text embeddings: {textdb.count()}")
print(f"Image embeddings: {imgdb.count()}")

# Test similarity search
results = textdb.query(
    query_texts=["your search query"],
    n_results=5
)
```

## Advanced Configuration

### Model Switching

Modify [`settings.py`](utils/settings.py) to use different models:

```python
# For different vision capabilities
VISION_MODEL = "llava"  # Alternative vision model
VISION_MODEL = "qwen2.5vl:32b"  # Smaller version

# For different embedding models  
EMBEDDING_MODEL = "nomic-embed-text"  # Alternative embedding model
```

### Custom Processing Scripts

The system provides several preprocessing utilities:

1. **[`process_manual.py`](tests/process_manual.py)**: Adjusts heading hierarchy and converts to XML
2. **[`adjust_headings_and_convert_to_xml.py`](tests/adjust_headings_and_convert_to_xml.py)**: Advanced heading structure analysis

### Performance Optimization

1. **Batch Processing**: The system uses progress bars and batch operations for efficiency
2. **Error Handling**: Failed items are logged and skipped to prevent pipeline interruption
3. **Memory Management**: Large documents are processed page by page to manage memory usage

## Troubleshooting

### Common Issues

1. **File Path Errors**: Ensure `.data/result/manual/` directory exists with required files
2. **Model Availability**: Verify that required models are installed in Ollama
3. **Memory Issues**: For large documents, consider processing in smaller batches
4. **Image Processing Failures**: Check image file formats and accessibility

### Logs and Monitoring

The system provides detailed logging:
- Processing progress with progress bars
- Success/failure messages for each item
- Error details for debugging

### Database Reset

To reset and reprocess:
```python
# Clear existing databases
textdb = get_database("textdb")
imgdb = get_database("imgdb") 

# Note: ChromaDB doesn't have a direct clear method
# You may need to delete the database directory and recreate
```

## Best Practices

1. **Data Preparation**: Ensure high-quality input JSON and markdown files
2. **Iterative Improvement**: Process small batches first, verify quality, then scale up
3. **Context Preservation**: Maintain page-level organization for better context extraction
4. **Quality Control**: Always verify a sample of outputs before processing large document sets
5. **Backup Strategy**: Keep original files and intermediate outputs for rollback capability

This guide provides a comprehensive workflow for document processing with emphasis on quality control and customization options. The modular design allows for easy adaptation to different document types and requirements.