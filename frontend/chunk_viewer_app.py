#!/usr/bin/env python3
"""
Flask web application for document chunk visualization
Displays original markdown document alongside stored database chunks
"""

import sys
import pathlib
import json
from flask import Flask, render_template, jsonify, request
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_database import get_database


@dataclass
class StoredChunk:
    """Information about a chunk stored in the database"""
    content: str
    metadata: Dict
    chunk_id: str
    page_idx: int = 0
    chunk_type: str = "text"
    summary: str = ""
    path: str = ""


@dataclass
class ChunkMapping:
    """Mapping between database chunk and original document position"""
    stored_chunk: StoredChunk
    start_pos: int = -1
    end_pos: int = -1
    match_score: float = 0.0


class DatabaseChunkViewer:
    """Backend class to handle database chunks and document mapping"""
    
    def __init__(self):
        self.original_text = ""
        self.stored_chunks = []
        self.chunk_mappings = []
        
        # Initialize database connections
        try:
            self.textdb = get_database("textdb")
            self.imgdb = get_database("imgdb")
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            self.textdb = None
            self.imgdb = None
    
    def load_document(self, text: str) -> None:
        """Load the original document text"""
        self.original_text = text
        
    def load_stored_chunks(self) -> bool:
        """Load chunks from database"""
        self.stored_chunks = []
        
        if not self.textdb or not self.imgdb:
            return False
            
        try:
            # Load text chunks
            text_results = self.textdb.get()
            if text_results and text_results['documents']:
                for doc, metadata, chunk_id in zip(
                    text_results['documents'], 
                    text_results['metadatas'], 
                    text_results['ids']
                ):
                    chunk = StoredChunk(
                        content=doc,
                        metadata=metadata or {},
                        chunk_id=chunk_id,
                        page_idx=metadata.get('page_idx', 0) if metadata else 0,
                        chunk_type="text",
                        summary=metadata.get('summary', '') if metadata else '',
                        path=metadata.get('path', '') if metadata else ''
                    )
                    self.stored_chunks.append(chunk)
            
            # Load image/table chunks  
            img_results = self.imgdb.get()
            if img_results and img_results['documents']:
                for doc, metadata, chunk_id in zip(
                    img_results['documents'], 
                    img_results['metadatas'], 
                    img_results['ids']
                ):
                    chunk_type = metadata.get('type', 'image') if metadata else 'image'
                    chunk = StoredChunk(
                        content=doc,
                        metadata=metadata or {},
                        chunk_id=chunk_id,
                        page_idx=metadata.get('page_idx', 0) if metadata else 0,
                        chunk_type=chunk_type,
                        summary=metadata.get('summary', '') if metadata else '',
                        path=metadata.get('path', '') if metadata else ''
                    )
                    self.stored_chunks.append(chunk)
                    
            return True
                    
        except Exception as e:
            print(f"Error loading chunks from database: {e}")
            return False
    
    def map_chunks_to_document(self) -> None:
        """Map stored chunks to positions in the original document"""
        self.chunk_mappings = []
        
        if not self.original_text or not self.stored_chunks:
            return
            
        for chunk in self.stored_chunks:
            if chunk.chunk_type == "text":
                mapping = self._find_chunk_position(chunk)
                self.chunk_mappings.append(mapping)
            else:
                # For images/tables, they don't map to text positions
                mapping = ChunkMapping(
                    stored_chunk=chunk,
                    start_pos=-1,
                    end_pos=-1,
                    match_score=1.0
                )
                self.chunk_mappings.append(mapping)
    
    def _find_chunk_position(self, chunk: StoredChunk) -> ChunkMapping:
        """Find the position of a chunk in the original document"""
        chunk_content = chunk.content.strip()
        
        # Try exact match first
        start_pos = self.original_text.find(chunk_content)
        if start_pos != -1:
            return ChunkMapping(
                stored_chunk=chunk,
                start_pos=start_pos,
                end_pos=start_pos + len(chunk_content),
                match_score=1.0
            )
        
        # Try fuzzy matching with first and last sentences
        lines = chunk_content.split('\n')
        if len(lines) >= 2:
            first_line = lines[0].strip()
            last_line = lines[-1].strip()
            
            first_pos = self.original_text.find(first_line)
            if first_pos != -1:
                search_start = first_pos + len(first_line)
                last_pos = self.original_text.find(last_line, search_start)
                
                if last_pos != -1:
                    return ChunkMapping(
                        stored_chunk=chunk,
                        start_pos=first_pos,
                        end_pos=last_pos + len(last_line),
                        match_score=0.8
                    )
        
        # Try matching first 50 characters
        prefix = chunk_content[:50].strip()
        if prefix:
            pos = self.original_text.find(prefix)
            if pos != -1:
                estimated_end = pos + len(chunk_content)
                return ChunkMapping(
                    stored_chunk=chunk,
                    start_pos=pos,
                    end_pos=min(estimated_end, len(self.original_text)),
                    match_score=0.6
                )
        
        # No match found
        return ChunkMapping(
            stored_chunk=chunk,
            start_pos=-1,
            end_pos=-1,
            match_score=0.0
        )
    
    def get_highlighted_document(self) -> Dict:
        """Get document with highlighted chunks for frontend"""
        if not self.chunk_mappings or not self.original_text:
            return {
                "original_text": self.original_text,
                "highlighted_segments": []
            }
        
        # Sort mappings by start position (only valid ones)
        valid_mappings = [m for m in self.chunk_mappings if m.start_pos >= 0]
        sorted_mappings = sorted(valid_mappings, key=lambda x: x.start_pos)
        
        segments = []
        last_end = 0
        
        for i, mapping in enumerate(sorted_mappings):
            # Add text before this chunk
            if mapping.start_pos > last_end:
                segments.append({
                    "type": "text",
                    "content": self.original_text[last_end:mapping.start_pos],
                    "start": last_end,
                    "end": mapping.start_pos
                })
            
            # Add chunk segment
            segments.append({
                "type": "chunk",
                "content": self.original_text[mapping.start_pos:mapping.end_pos],
                "start": mapping.start_pos,
                "end": mapping.end_pos,
                "chunk_index": i,
                "chunk_id": mapping.stored_chunk.chunk_id,
                "chunk_type": mapping.stored_chunk.chunk_type,
                "page_idx": mapping.stored_chunk.page_idx,
                "match_score": mapping.match_score
            })
            
            last_end = mapping.end_pos
        
        # Add remaining text
        if last_end < len(self.original_text):
            segments.append({
                "type": "text", 
                "content": self.original_text[last_end:],
                "start": last_end,
                "end": len(self.original_text)
            })
            
        return {
            "original_text": self.original_text,
            "segments": segments
        }
    
    def get_chunks_data(self) -> List[Dict]:
        """Get formatted chunks data for frontend"""
        chunks_data = []
        
        for i, mapping in enumerate(self.chunk_mappings):
            chunk = mapping.stored_chunk
            chunks_data.append({
                "index": i,
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "chunk_type": chunk.chunk_type,
                "page_idx": chunk.page_idx,
                "start_pos": mapping.start_pos,
                "end_pos": mapping.end_pos,
                "match_score": mapping.match_score,
                "path": chunk.path,
                "summary": chunk.summary
            })
            
        return chunks_data


# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
viewer = DatabaseChunkViewer()


@app.route('/')
def index():
    """Main page"""
    return render_template('chunk_viewer.html')


@app.route('/api/load', methods=['POST'])
def load_data():
    """Load document and database chunks"""
    data = request.get_json()
    markdown_path = data.get('markdown_path', '.data/result/manual/manual.md')
    
    try:
        # Load markdown file
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        viewer.load_document(markdown_content)
        
        # Load chunks from database
        if not viewer.load_stored_chunks():
            return jsonify({
                'success': False,
                'error': 'Failed to load chunks from database'
            })
        
        # Map chunks to document
        viewer.map_chunks_to_document()
        
        # Get statistics
        total_chunks = len(viewer.stored_chunks)
        text_chunks = len([c for c in viewer.stored_chunks if c.chunk_type == 'text'])
        mapped_chunks = len([m for m in viewer.chunk_mappings if m.start_pos >= 0])
        
        return jsonify({
            'success': True,
            'stats': {
                'document_length': len(markdown_content),
                'total_chunks': total_chunks,
                'text_chunks': text_chunks,
                'mapped_chunks': mapped_chunks,
                'unmapped_chunks': total_chunks - mapped_chunks
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/document')
def get_document():
    """Get highlighted document data"""
    try:
        return jsonify(viewer.get_highlighted_document())
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/chunks')
def get_chunks():
    """Get chunks data"""
    try:
        return jsonify(viewer.get_chunks_data())
    except Exception as e:
        return jsonify({'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)