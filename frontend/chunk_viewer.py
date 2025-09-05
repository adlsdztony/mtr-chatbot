import sys
import pathlib
import streamlit as st
import json
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_database import get_database
import chromadb


@dataclass
class StoredChunk:
    """Information about a chunk stored in the database"""
    content: str
    metadata: Dict
    chunk_id: str
    page_idx: int = 0
    chunk_type: str = "text"  # text, image, table
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
    """A class to view chunks stored in database and map them to original document"""
    
    def __init__(self):
        self.original_text = ""
        self.stored_chunks = []
        self.chunk_mappings = []
        self.json_data = []
        
        # Initialize database connections
        try:
            self.textdb = get_database("textdb")
            self.imgdb = get_database("imgdb")
        except Exception as e:
            st.error(f"Failed to connect to database: {e}")
            self.textdb = None
            self.imgdb = None
        
    def load_document(self, text: str) -> None:
        """Load the original document text"""
        self.original_text = text
        
    def load_stored_chunks(self) -> None:
        """Load chunks from database"""
        self.stored_chunks = []
        
        if not self.textdb or not self.imgdb:
            st.error("Database not available")
            return
            
        try:
            # Load text chunks
            text_results = self.textdb.get()
            if text_results and text_results['documents']:
                for i, (doc, metadata, chunk_id) in enumerate(zip(
                    text_results['documents'], 
                    text_results['metadatas'], 
                    text_results['ids']
                )):
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
                for i, (doc, metadata, chunk_id) in enumerate(zip(
                    img_results['documents'], 
                    img_results['metadatas'], 
                    img_results['ids']
                )):
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
                    
        except Exception as e:
            st.error(f"Error loading chunks from database: {e}")
    
    def map_chunks_to_document(self) -> None:
        """Map stored chunks to positions in the original document"""
        self.chunk_mappings = []
        
        if not self.original_text or not self.stored_chunks:
            return
            
        for chunk in self.stored_chunks:
            if chunk.chunk_type == "text":
                # Try to find this chunk content in the original document
                mapping = self._find_chunk_position(chunk)
                self.chunk_mappings.append(mapping)
            else:
                # For images/tables, we'll show them separately
                mapping = ChunkMapping(
                    stored_chunk=chunk,
                    start_pos=-1,
                    end_pos=-1,
                    match_score=1.0  # Consider non-text items as perfectly matched
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
            
            # Look for the first line
            first_pos = self.original_text.find(first_line)
            if first_pos != -1:
                # Try to find a reasonable end position
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
                # Estimate end position
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
    
    def get_highlighted_text(self) -> str:
        """Get original text with chunk boundaries highlighted based on stored chunks"""
        if not self.chunk_mappings or not self.original_text:
            return self._escape_html(self.original_text)
            
        # Sort mappings by start position (only those with valid positions)
        valid_mappings = [m for m in self.chunk_mappings if m.start_pos >= 0]
        sorted_mappings = sorted(valid_mappings, key=lambda x: x.start_pos)
        
        # Build highlighted text
        highlighted = ""
        last_end = 0
        
        for i, mapping in enumerate(sorted_mappings):
            chunk = mapping.stored_chunk
            
            # Add text before this chunk
            if mapping.start_pos > last_end:
                text_between = self.original_text[last_end:mapping.start_pos]
                highlighted += self._escape_html(text_between)
            
            # Add highlighted chunk with boundary markers
            chunk_color = self._get_chunk_color(i)
            confidence_indicator = self._get_confidence_indicator(mapping.match_score)
            
            highlighted += f'<div style="border-left: 4px solid {chunk_color}; padding-left: 8px; margin: 4px 0; background-color: {chunk_color}20; border-radius: 4px;" id="chunk-{i}">'
            highlighted += f'<div style="color: {chunk_color}; font-weight: bold; font-size: 12px; margin-bottom: 4px; padding: 2px 6px; background: {chunk_color}40; border-radius: 3px; display: inline-block;">'
            highlighted += f'Chunk {i+1} ({chunk.chunk_type}) - {len(chunk.content)} chars {confidence_indicator}'
            highlighted += f'<br><small>ID: {chunk.chunk_id} | Page: {chunk.page_idx}</small>'
            highlighted += '</div><br>'
            
            # Show the actual content from the mapped region
            if mapping.end_pos > mapping.start_pos:
                mapped_content = self.original_text[mapping.start_pos:mapping.end_pos]
                highlighted += self._escape_html(mapped_content)
            else:
                highlighted += f'<em style="color: #888;">[Content not found in original document]</em>'
            
            highlighted += '</div>'
            
            last_end = max(last_end, mapping.end_pos) if mapping.end_pos > 0 else last_end
        
        # Add remaining text
        if last_end < len(self.original_text):
            remaining_text = self.original_text[last_end:]
            highlighted += self._escape_html(remaining_text)
            
        return highlighted
    
    def _get_confidence_indicator(self, score: float) -> str:
        """Get a visual indicator for mapping confidence"""
        if score >= 1.0:
            return "✅"  # Perfect match
        elif score >= 0.8:
            return "🟡"  # Good match
        elif score >= 0.6:
            return "🟠"  # Partial match
        else:
            return "❌"  # No match
    
    def get_database_statistics(self) -> Dict:
        """Get statistics about the stored chunks"""
        if not self.stored_chunks:
            return {}
            
        stats = {
            'total_chunks': len(self.stored_chunks),
            'text_chunks': len([c for c in self.stored_chunks if c.chunk_type == 'text']),
            'image_chunks': len([c for c in self.stored_chunks if c.chunk_type == 'image']),
            'table_chunks': len([c for c in self.stored_chunks if c.chunk_type == 'table']),
            'pages': set(c.page_idx for c in self.stored_chunks),
            'avg_text_length': 0,
            'mapped_chunks': len([m for m in self.chunk_mappings if m.start_pos >= 0]),
            'unmapped_chunks': len([m for m in self.chunk_mappings if m.start_pos < 0])
        }
        
        text_chunks = [c for c in self.stored_chunks if c.chunk_type == 'text']
        if text_chunks:
            stats['avg_text_length'] = sum(len(c.content) for c in text_chunks) / len(text_chunks)
            
        stats['pages'] = sorted(list(stats['pages']))
        return stats
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML characters and preserve formatting"""
        # Basic HTML escaping
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
        
        # Convert newlines to <br> tags
        text = text.replace('\n', '<br>')
        
        return text
    
    def _get_chunk_color(self, chunk_index: int) -> str:
        """Get a color for the chunk based on its index"""
        colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
            "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9"
        ]
        return colors[chunk_index % len(colors)]


def load_sample_data() -> Tuple[str, List[Dict]]:
    """Load sample markdown and JSON data if available"""
    try:
        # Try to load from the default paths used in run_embedding.py
        json_path = ".data/result/manual/manual_content_list.json"
        markdown_path = ".data/result/manual/manual.md"
        
        markdown_text = ""
        json_data = []
        
        # Try to load markdown
        try:
            with open(markdown_path, "r", encoding="utf-8") as f:
                markdown_text = f.read()
        except FileNotFoundError:
            pass
            
        # Try to load JSON
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except FileNotFoundError:
            pass
            
        return markdown_text, json_data
        
    except Exception as e:
        st.error(f"Error loading sample data: {e}")
        return "", []


def main():
    st.set_page_config(
        page_title="Database Chunk Viewer",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Database Chunk Viewer")
    st.markdown("View original documents alongside their stored chunks from the vector database")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # File path inputs
        st.subheader("Document Paths")
        markdown_path = st.text_input(
            "Markdown file path:",
            value=".data/result/manual/manual.md",
            help="Path to the original markdown document"
        )
        
        json_path = st.text_input(
            "JSON file path:",
            value=".data/result/manual/manual_content_list.json",
            help="Path to the processed JSON data (optional)"
        )
        
        st.markdown("---")
        
        # Database operations
        st.subheader("💾 Database Operations")
        
        if st.button("🔄 Load Data", type="primary"):
            st.session_state.load_requested = True
        
        if st.button("🗑️ Clear Cache"):
            st.session_state.clear()
            st.success("Cache cleared!")
    
    # Initialize the viewer
    if 'viewer' not in st.session_state:
        st.session_state.viewer = DatabaseChunkViewer()
    
    # Load data when requested
    if hasattr(st.session_state, 'load_requested') and st.session_state.load_requested:
        with st.spinner("Loading data..."):
            # Load markdown file
            try:
                with open(markdown_path, "r", encoding="utf-8") as f:
                    markdown_content = f.read()
                st.session_state.viewer.load_document(markdown_content)
                st.success(f"Loaded markdown document ({len(markdown_content):,} characters)")
            except Exception as e:
                st.error(f"Failed to load markdown file: {e}")
                return
            
            # Load JSON data if available
            if json_path:
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        json_data = json.load(f)
                    st.session_state.json_data = json_data
                    st.success(f"Loaded JSON data ({len(json_data)} items)")
                except Exception as e:
                    st.warning(f"Could not load JSON file: {e}")
            
            # Load chunks from database
            st.session_state.viewer.load_stored_chunks()
            st.session_state.viewer.map_chunks_to_document()
            
            st.session_state.load_requested = False
    
    # Check if data is loaded
    if not hasattr(st.session_state.viewer, 'original_text') or not st.session_state.viewer.original_text:
        st.info("👆 Please load your data using the sidebar controls")
        
        # Show example
        st.markdown("### 💡 How to use this tool")
        st.markdown("""
        This tool displays your original markdown document alongside the chunks that have been 
        stored in your vector database:
        
        1. **Enter file paths** in the sidebar for your markdown and JSON files
        2. **Click 'Load Data'** to load the document and fetch chunks from the database  
        3. **View the comparison** between original content and stored chunks
        4. **Analyze the mapping** to see how well chunks correspond to the original text
        
        The tool will show:
        - Original document with highlighted chunk boundaries
        - Individual stored chunks with metadata
        - Statistics about chunk distribution and mapping quality
        """)
        return
    
    # Display statistics
    st.header("📊 Database Statistics")
    db_stats = st.session_state.viewer.get_database_statistics()
    
    if db_stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Chunks", db_stats['total_chunks'])
        with col2:
            st.metric("Text Chunks", db_stats['text_chunks'])
        with col3:
            st.metric("Images/Tables", db_stats['image_chunks'] + db_stats['table_chunks'])
        with col4:
            st.metric("Pages", len(db_stats['pages']))
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mapped to Document", db_stats['mapped_chunks'])
        with col2:
            st.metric("Not Mapped", db_stats['unmapped_chunks'])
        with col3:
            if db_stats['text_chunks'] > 0:
                st.metric("Avg Text Length", f"{db_stats['avg_text_length']:.0f} chars")
    
    # Main content area with two columns
    st.header("📝 Document & Chunks Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 Original Document with Stored Chunks")
        # Add scroll sync JavaScript
        st.markdown("""
        <script>
        function syncScroll(source, target) {
            var sourceElement = document.getElementById(source);
            var targetElement = document.getElementById(target);
            if (sourceElement && targetElement) {
                var scrollPercentage = sourceElement.scrollTop / (sourceElement.scrollHeight - sourceElement.clientHeight);
                targetElement.scrollTop = scrollPercentage * (targetElement.scrollHeight - targetElement.clientHeight);
            }
        }
        </script>
        """, unsafe_allow_html=True)
        
        highlighted_text = st.session_state.viewer.get_highlighted_text()
        st.markdown(
            f'''<div id="original-doc" style="
                height: 600px; 
                overflow-y: scroll; 
                padding: 10px; 
                border: 1px solid #ddd; 
                border-radius: 5px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                onscroll="syncScroll('original-doc', 'chunks-container')"
            ">{highlighted_text}</div>''',
            unsafe_allow_html=True
        )
    
    with col2:
        st.subheader("🧩 Stored Database Chunks")
        
        # Create a container for chunks with scroll
        chunks_container = st.container()
        
        with chunks_container:
            chunks_html = ""
            for i, mapping in enumerate(st.session_state.viewer.chunk_mappings):
                chunk = mapping.stored_chunk
                chunk_color = st.session_state.viewer._get_chunk_color(i)
                confidence = st.session_state.viewer._get_confidence_indicator(mapping.match_score)
                
                chunks_html += f'''
                <div style="
                    border: 2px solid {chunk_color};
                    border-radius: 8px;
                    padding: 12px;
                    margin: 8px 0;
                    background-color: {chunk_color}10;
                ">
                    <div style="
                        color: {chunk_color};
                        font-weight: bold;
                        font-size: 14px;
                        margin-bottom: 8px;
                    ">
                        Chunk {i+1} ({chunk.chunk_type}) {confidence}
                        <span style="color: #666; font-weight: normal; font-size: 12px;">
                            | ID: {chunk.chunk_id} | Page: {chunk.page_idx} | {len(chunk.content)} chars
                        </span>
                    </div>
                    <div style="
                        font-family: monospace;
                        font-size: 13px;
                        line-height: 1.4;
                        white-space: pre-wrap;
                        max-height: 200px;
                        overflow-y: auto;
                        background: #f8f9fa;
                        padding: 8px;
                        border-radius: 4px;
                    ">
                        {st.session_state.viewer._escape_html(chunk.content[:500])}{'...' if len(chunk.content) > 500 else ''}
                    </div>
                </div>
                '''
            
            st.markdown(
                f'''<div id="chunks-container" style="
                    height: 600px; 
                    overflow-y: scroll;
                    onscroll="syncScroll('chunks-container', 'original-doc')"
                ">{chunks_html}</div>''',
                unsafe_allow_html=True
            )
    
    # Additional analysis
    st.header("🔍 Detailed Analysis")
    
    with st.expander("View Individual Chunk Details", expanded=False):
        for i, mapping in enumerate(st.session_state.viewer.chunk_mappings):
            chunk = mapping.stored_chunk
            st.markdown(f"**Chunk {i+1} ({chunk.chunk_type})**")
            st.markdown(f"- **ID:** {chunk.chunk_id}")
            st.markdown(f"- **Page:** {chunk.page_idx}")
            st.markdown(f"- **Length:** {len(chunk.content)} characters")
            st.markdown(f"- **Mapping Score:** {mapping.match_score:.2f} {st.session_state.viewer._get_confidence_indicator(mapping.match_score)}")
            if mapping.start_pos >= 0:
                st.markdown(f"- **Position in Document:** {mapping.start_pos} - {mapping.end_pos}")
            else:
                st.markdown(f"- **Position:** Not found in original document")
            
            if chunk.path:
                st.markdown(f"- **Path:** {chunk.path}")
            
            if chunk.summary and chunk.summary != chunk.content:
                st.markdown(f"- **Summary:** {chunk.summary[:200]}...")
            
            with st.expander(f"Full Content (Chunk {i+1})"):
                st.text(chunk.content)
            
            st.markdown("---")
    
    # Unmapped chunks analysis
    unmapped = [m for m in st.session_state.viewer.chunk_mappings if m.start_pos < 0]
    if unmapped:
        st.subheader(f"⚠️ Unmapped Chunks ({len(unmapped)})")
        st.markdown("These chunks from the database could not be mapped to the original document:")
        
        for i, mapping in enumerate(unmapped):
            chunk = mapping.stored_chunk
            with st.expander(f"Unmapped Chunk: {chunk.chunk_id} ({chunk.chunk_type})"):
                st.markdown(f"**Type:** {chunk.chunk_type}")
                st.markdown(f"**Page:** {chunk.page_idx}")
                st.markdown(f"**Length:** {len(chunk.content)} characters")
                if chunk.path:
                    st.markdown(f"**Path:** {chunk.path}")
                st.text_area("Content:", chunk.content, height=100, key=f"unmapped_{i}")


if __name__ == "__main__":
    main()