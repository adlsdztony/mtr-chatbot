import sys
import pathlib
import chromadb
from flask import Flask, render_template, jsonify, send_file, abort, request
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


@app.route('/api/files')
def get_available_files():
    """Get list of available files from database"""
    try:
        available_files = set()

        available_files.add("manual")  # Always include 'manual' as a default option
        
        # Check both textdb and imgdb for filenames
        for collection_name in ['textdb', 'imgdb']:
            try:
                collection = storage.get_collection(name=collection_name)
                result = collection.get(include=['metadatas'])
                
                for metadata in result['metadatas']:
                    if metadata and 'filename' in metadata:
                        available_files.add(metadata['filename'])
            except Exception as e:
                print(f"Error checking {collection_name}: {e}")
        
        return jsonify({
            'success': True,
            'files': sorted(list(available_files))
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/chunks')
def get_chunks():
    """Get chunks from both collections, optionally filtered by filename"""
    filename = request.args.get('filename')
    
    try:
        all_chunks = []
        
        # Get chunks from textdb
        try:
            textdb = storage.get_collection(name='textdb')
            text_result = textdb.get(include=['documents', 'metadatas'])
            
            for i in range(len(text_result['ids'])):
                metadata = text_result['metadatas'][i] if text_result['metadatas'] else {}
                
                # Filter by filename if specified
                if filename and metadata.get('filename') != filename:
                    continue
                
                chunk = {
                    'id': text_result['ids'][i],
                    'document': text_result['documents'][i] if text_result['documents'] else None,
                    'metadata': metadata,
                    'source': 'textdb'
                }
                all_chunks.append(chunk)
        except Exception as e:
            print(f"Error loading textdb: {e}")
        
        # Get chunks from imgdb
        try:
            imgdb = storage.get_collection(name='imgdb')
            img_result = imgdb.get(include=['documents', 'metadatas'])
            
            for i in range(len(img_result['ids'])):
                metadata = img_result['metadatas'][i] if img_result['metadatas'] else {}
                
                # Filter by filename if specified
                if filename and metadata.get('filename') != filename:
                    continue
                
                chunk = {
                    'id': img_result['ids'][i],
                    'document': img_result['documents'][i] if img_result['documents'] else None,
                    'metadata': metadata,
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
            'chunks': all_chunks,
            'filename': filename
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve images from the data directory"""
    doc_name = request.args.get('doc', 'manual')
    
    # Try multiple possible locations for the image
    possible_paths = [
        PROJECT_ROOT / ".data" / "result" / doc_name / "images" / filename,
        PROJECT_ROOT / ".data" / "result" / doc_name / filename,
        PROJECT_ROOT / ".data" / "result" / "manual" / "images" / filename,  # fallback to manual
        PROJECT_ROOT / ".data" / "result" / "manual" / filename
    ]
    
    image_path = None
    for path in possible_paths:
        if path.exists():
            image_path = path
            break
    
    if not image_path:
        abort(404, description=f"Image not found: {filename} for document: {doc_name}")
    
    # Serve the file
    try:
        return send_file(str(image_path), mimetype='image/jpeg')
    except Exception as e:
        abort(500, description=str(e))

@app.route('/api/pdf')
def serve_pdf():
    """Serve the PDF document based on filename parameter"""
    filename = request.args.get('filename', 'manual')
    
    # Try multiple possible locations for the PDF
    possible_paths = [
        PROJECT_ROOT / ".data" / "original" / f"{filename}.pdf",
        PROJECT_ROOT / ".data" / "result" / filename / f"{filename}.pdf", 
        PROJECT_ROOT / ".data" / "result" / filename / f"{filename}_origin.pdf"
    ]
    
    pdf_path = None
    for path in possible_paths:
        if path.exists():
            pdf_path = path
            break
    
    if not pdf_path:
        return jsonify({
            'success': False,
            'error': f'PDF not found for filename: {filename}. Tried: {[str(p) for p in possible_paths]}'
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