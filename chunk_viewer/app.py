import sys
import pathlib
import chromadb
from flask import Flask, render_template, jsonify, send_file, abort
from flask_cors import CORS
import os

# Get the base paths relative to this file
CURRENT_DIR = pathlib.Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent

# Add parent directory to path to access main project modules
sys.path.append(str(PROJECT_ROOT))

from utils import get_database, settings

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Initialize ChromaDB client - path relative to main project
DB_PATH = PROJECT_ROOT / "database" / "storage"
storage = chromadb.PersistentClient(str(DB_PATH))

@app.route('/')
def index():
    """Render the main chunk viewer page"""
    return render_template('index.html')

@app.route('/api/document')
def get_document():
    """Get the original markdown document"""
    markdown_path = PROJECT_ROOT / ".data" / "result" / "manual" / "manual.md"
    try:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({
            'success': True,
            'content': content,
            'path': str(markdown_path.relative_to(PROJECT_ROOT))
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'Document not found: {markdown_path}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/chunks/<collection_name>')
def get_chunks(collection_name):
    """Get all chunks from a specific collection"""
    try:
        # Get the collection
        collection = storage.get_collection(name=collection_name)
        
        # Retrieve all documents
        result = collection.get(
            include=['documents', 'metadatas']
        )
        
        # Format the response
        chunks = []
        for i in range(len(result['ids'])):
            chunk = {
                'id': result['ids'][i],
                'document': result['documents'][i] if result['documents'] else None,
                'metadata': result['metadatas'][i] if result['metadatas'] else None
            }
            chunks.append(chunk)
        
        return jsonify({
            'success': True,
            'collection': collection_name,
            'count': len(chunks),
            'chunks': chunks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/collections')
def get_collections():
    """Get all available collections"""
    try:
        collections = storage.list_collections()
        collection_names = [col.name for col in collections]
        return jsonify({
            'success': True,
            'collections': collection_names
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/chunk/<collection_name>/<chunk_id>')
def get_chunk_detail(collection_name, chunk_id):
    """Get detailed information about a specific chunk"""
    try:
        collection = storage.get_collection(name=collection_name)
        result = collection.get(
            ids=[chunk_id],
            include=['documents', 'metadatas', 'embeddings']
        )
        
        if not result['ids']:
            return jsonify({
                'success': False,
                'error': 'Chunk not found'
            }), 404
        
        chunk = {
            'id': result['ids'][0],
            'document': result['documents'][0] if result['documents'] else None,
            'metadata': result['metadatas'][0] if result['metadatas'] else None,
            'embedding_size': len(result['embeddings'][0]) if result['embeddings'] and result['embeddings'][0] else 0
        }
        
        return jsonify({
            'success': True,
            'chunk': chunk
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/search/<collection_name>')
def search_chunks(collection_name):
    """Search for chunks containing specific text"""
    from flask import request
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Query parameter is required'
        }), 400
    
    try:
        collection = storage.get_collection(name=collection_name)
        
        # Get all chunks and filter by query
        result = collection.get(
            include=['documents', 'metadatas']
        )
        
        matching_chunks = []
        for i in range(len(result['ids'])):
            doc = result['documents'][i] if result['documents'] else ''
            if query.lower() in str(doc).lower():
                chunk = {
                    'id': result['ids'][i],
                    'document': doc,
                    'metadata': result['metadatas'][i] if result['metadatas'] else None
                }
                matching_chunks.append(chunk)
        
        return jsonify({
            'success': True,
            'query': query,
            'count': len(matching_chunks),
            'chunks': matching_chunks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve images from the data directory"""
    # Construct the full path to the image - relative to main project
    image_path = PROJECT_ROOT / ".data" / "result" / "manual" / "images" / filename
    
    # Check if file exists
    if not image_path.exists():
        # Try without the images prefix if it's already in the filename
        alt_path = PROJECT_ROOT / ".data" / "result" / "manual" / filename
        if alt_path.exists():
            image_path = alt_path
        else:
            abort(404, description="Image not found")
    
    # Serve the file
    try:
        return send_file(str(image_path), mimetype='image/jpeg')
    except Exception as e:
        abort(500, description=str(e))

if __name__ == '__main__':
    app.run(debug=True, port=5000)