# Chunk Viewer - Document Chunk Debugging Tool

A clean, minimal web interface for visualizing and debugging document chunks created by the MinerU markdown processing pipeline.

## Features

- **Dual Panel View**: Side-by-side display of original markdown document and extracted chunks
- **Interactive Chunk Selection**: Click on any chunk to highlight its source in the original document
- **Collection Support**: Switch between different ChromaDB collections (textdb, imgdb)
- **Search Functionality**: Search for specific text within chunks
- **Detailed Chunk Information**: View metadata, page index, type, and full content of each chunk
- **Clean UI**: Minimal gray-white theme for comfortable debugging sessions

## Prerequisites

- Python environment with required packages installed
- ChromaDB database with embedded chunks (run `uv run python tests/run_embedding.py` first)
- Original markdown document at `.data/result/manual/manual.md`

## Installation

The chunk viewer uses Flask and requires no additional dependencies beyond what's already in the project.

## Usage

### 1. Check Database Status

First, verify that chunks exist in the database:

```bash
uv run python check_chunks.py
```

This will show:
- Available collections
- Number of chunks in each collection
- Sample chunks with metadata

### 2. Launch the Viewer

```bash
uv run python run_chunk_viewer.py
```

Or directly:

```bash
uv run python chunk_viewer.py
```

The viewer will start on `http://localhost:5000` and automatically open in your browser.

### 3. Using the Interface

#### Navigation
- **Select Collection**: Choose between `textdb` (text chunks) or `imgdb` (images/tables)
- **Search**: Enter keywords to filter chunks
- **Refresh**: Reload the current view
- **Clear Highlights**: Remove all text highlights from the document

#### Viewing Chunks
1. Select a collection from the dropdown
2. Browse chunks in the right panel
3. Click on a chunk to:
   - Highlight its source in the original document (if found)
   - View detailed information in a modal
   - See metadata including page index and type

#### Chunk Types
- **Text** (green): Regular text content chunks
- **Image** (orange): Image-based content with summaries
- **Table** (purple): Table data with summaries

## API Endpoints

The Flask backend provides these endpoints:

- `GET /` - Main UI interface
- `GET /api/document` - Retrieve original markdown document
- `GET /api/collections` - List available collections
- `GET /api/chunks/<collection>` - Get all chunks from a collection
- `GET /api/chunk/<collection>/<id>` - Get specific chunk details
- `GET /api/search/<collection>?q=<query>` - Search chunks

## File Structure

```
mtr-chatbot/
├── chunk_viewer.py                 # Flask backend
├── chunk_viewer_templates/
│   └── index.html                 # HTML template
├── chunk_viewer_static/
│   ├── css/
│   │   └── style.css             # Styling
│   └── js/
│       └── app.js                # Frontend logic
├── check_chunks.py                # Database inspection tool
└── run_chunk_viewer.py           # Launch script
```

## Troubleshooting

### No chunks displayed
- Run `check_chunks.py` to verify database has data
- Ensure you've run the embedding script first: `uv run python tests/run_embedding.py`

### Document not loading
- Check that `.data/result/manual/manual.md` exists
- Verify the path in `chunk_viewer.py` if using a different document

### Connection errors
- Ensure port 5000 is available
- Check that ChromaDB storage path is correct: `database/storage`

## Development

To modify the viewer:

1. **Backend**: Edit `chunk_viewer.py` for API changes
2. **Frontend**: Modify files in `chunk_viewer_static/` for UI changes
3. **Styling**: Update `style.css` for theme modifications

The viewer uses:
- Flask for backend API
- Vanilla JavaScript for frontend (no framework dependencies)
- Marked.js for markdown rendering
- ChromaDB for vector database operations

## Notes

- The viewer is designed for debugging and development purposes
- Chunk highlighting works best with exact text matches
- Large documents may take a moment to render
- The search function performs client-side filtering for simplicity