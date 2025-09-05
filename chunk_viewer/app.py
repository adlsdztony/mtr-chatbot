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


@app.route('/api/chunks')
def get_all_chunks():
    """Get all chunks from both textdb and imgdb collections"""
    try:
        all_chunks = []
        
        # Get chunks from textdb
        try:
            textdb = storage.get_collection(name='textdb')
            text_result = textdb.get(
                include=['documents', 'metadatas']
            )
            
            for i in range(len(text_result['ids'])):
                chunk = {
                    'id': text_result['ids'][i],
                    'document': text_result['documents'][i] if text_result['documents'] else None,
                    'metadata': text_result['metadatas'][i] if text_result['metadatas'] else None,
                    'source': 'textdb'
                }
                all_chunks.append(chunk)
        except Exception as e:
            print(f"Error loading textdb: {e}")
        
        # Get chunks from imgdb
        try:
            imgdb = storage.get_collection(name='imgdb')
            img_result = imgdb.get(
                include=['documents', 'metadatas']
            )
            
            for i in range(len(img_result['ids'])):
                chunk = {
                    'id': img_result['ids'][i],
                    'document': img_result['documents'][i] if img_result['documents'] else None,
                    'metadata': img_result['metadatas'][i] if img_result['metadatas'] else None,
                    'source': 'imgdb'
                }
                all_chunks.append(chunk)
        except Exception as e:
            print(f"Error loading imgdb: {e}")
        
        # Sort chunks by page_idx
        all_chunks.sort(key=lambda x: (
            x.get('metadata', {}).get('page_idx', 999999),
            x.get('id', '')
        ))
        
        return jsonify({
            'success': True,
            'count': len(all_chunks),
            'chunks': all_chunks
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

@app.route('/api/pdf')
def serve_pdf():
    """Serve the PDF document"""
    pdf_path = PROJECT_ROOT / ".data" / "original" / "manual.pdf"
    
    if not pdf_path.exists():
        return jsonify({
            'success': False,
            'error': f'PDF not found at: {pdf_path}'
        }), 404
    
    try:
        return send_file(str(pdf_path), mimetype='application/pdf')
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)