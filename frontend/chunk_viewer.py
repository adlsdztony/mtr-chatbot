import sys
import pathlib
import streamlit as st
import json
import re
import markdown
from typing import List, Dict, Tuple
from dataclasses import dataclass

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from langchain.text_splitter import RecursiveCharacterTextSplitter


@dataclass
class ChunkInfo:
    """Information about a text chunk"""
    content: str
    start_pos: int
    end_pos: int
    chunk_id: int
    page_idx: int = 0


class DocumentChunkViewer:
    """A class to handle document chunking and visualization"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        self.original_text = ""
        self.chunks = []
        self.json_data = []
        
    def load_document(self, text: str) -> None:
        """Load the original document text"""
        self.original_text = text
        self._create_chunks()
        
    def load_json_data(self, json_data: List[Dict]) -> None:
        """Load and analyze JSON data from mineru processing"""
        self.json_data = json_data
        
    def analyze_json_structure(self) -> Dict:
        """Analyze the structure of the JSON data"""
        if not self.json_data:
            return {}
            
        analysis = {
            'total_items': len(self.json_data),
            'types': {},
            'pages': set(),
            'text_items': [],
            'image_items': [],
            'table_items': []
        }
        
        for item in self.json_data:
            item_type = item.get('type', 'unknown')
            page_idx = item.get('page_idx', 0)
            
            # Count types
            analysis['types'][item_type] = analysis['types'].get(item_type, 0) + 1
            
            # Track pages
            analysis['pages'].add(page_idx)
            
            # Categorize items
            if item_type == 'text':
                analysis['text_items'].append(item)
            elif item_type == 'image':
                analysis['image_items'].append(item)
            elif item_type == 'table':
                analysis['table_items'].append(item)
                
        analysis['pages'] = sorted(list(analysis['pages']))
        return analysis
        
    def _create_chunks(self) -> None:
        """Create chunks from the original text and track their positions"""
        self.chunks = []
        
        # Split text into chunks
        text_chunks = self.text_splitter.split_text(self.original_text)
        
        # Find position of each chunk in original text
        current_pos = 0
        for i, chunk in enumerate(text_chunks):
            # Find the chunk in the original text starting from current position
            chunk_start = self.original_text.find(chunk, current_pos)
            if chunk_start == -1:
                # If exact match not found, try finding partial match
                # This can happen due to text splitting logic
                words = chunk.split()[:5]  # Use first 5 words for search
                search_text = " ".join(words)
                chunk_start = self.original_text.find(search_text, current_pos)
                if chunk_start == -1:
                    chunk_start = current_pos
            
            chunk_end = chunk_start + len(chunk)
            
            chunk_info = ChunkInfo(
                content=chunk,
                start_pos=chunk_start,
                end_pos=chunk_end,
                chunk_id=i
            )
            self.chunks.append(chunk_info)
            
            # Update current position for next search
            current_pos = chunk_start + len(chunk) // 2  # Start from middle of current chunk
    
    def get_highlighted_text(self) -> str:
        """Get original text with chunk boundaries highlighted"""
        if not self.chunks:
            return self.original_text
            
        # Sort chunks by start position
        sorted_chunks = sorted(self.chunks, key=lambda x: x.start_pos)
        
        # Build highlighted text
        highlighted = ""
        last_end = 0
        
        for i, chunk in enumerate(sorted_chunks):
            # Add text before this chunk
            if chunk.start_pos > last_end:
                text_between = self.original_text[last_end:chunk.start_pos]
                highlighted += self._escape_html(text_between)
            
            # Add highlighted chunk with boundary markers
            chunk_color = self._get_chunk_color(i)
            highlighted += f'<div style="border-left: 4px solid {chunk_color}; padding-left: 8px; margin: 4px 0; background-color: {chunk_color}20; border-radius: 4px;" id="chunk-{i}">'
            highlighted += f'<div style="color: {chunk_color}; font-weight: bold; font-size: 12px; margin-bottom: 4px; padding: 2px 6px; background: {chunk_color}40; border-radius: 3px; display: inline-block;">Chunk {i+1} ({len(chunk.content)} chars)</div><br>'
            highlighted += self._escape_html(chunk.content)
            highlighted += '</div>'
            
            last_end = chunk.end_pos
        
        # Add remaining text
        if last_end < len(self.original_text):
            remaining_text = self.original_text[last_end:]
            highlighted += self._escape_html(remaining_text)
            
        return highlighted
    
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
        page_title="Document Chunk Viewer",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 Document Chunk Viewer")
    st.markdown("Visualize how text documents are split into chunks for embedding processing")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Chunking Configuration")
        
        chunk_size = st.slider(
            "Chunk Size",
            min_value=100,
            max_value=3000,
            value=1000,
            step=100,
            help="Maximum number of characters per chunk"
        )
        
        chunk_overlap = st.slider(
            "Chunk Overlap",
            min_value=0,
            max_value=500,
            value=200,
            step=50,
            help="Number of overlapping characters between chunks"
        )
        
        st.markdown("---")
        
        # Option to load sample data
        if st.button("🔄 Load Sample Data"):
            sample_markdown, sample_json_data = load_sample_data()
            if sample_markdown:
                st.session_state.input_text = sample_markdown
                st.session_state.json_data = sample_json_data
                st.success("Sample data loaded!")
            else:
                st.warning("No sample data found. Please provide your own text.")
    
    # Initialize the chunk viewer
    if 'viewer' not in st.session_state:
        st.session_state.viewer = DocumentChunkViewer(chunk_size, chunk_overlap)
    
    # Update chunk settings if changed
    if (hasattr(st.session_state.viewer, 'text_splitter') and 
        (st.session_state.viewer.text_splitter.chunk_size != chunk_size or
         st.session_state.viewer.text_splitter.chunk_overlap != chunk_overlap)):
        st.session_state.viewer = DocumentChunkViewer(chunk_size, chunk_overlap)
        if hasattr(st.session_state, 'input_text') and st.session_state.input_text:
            st.session_state.viewer.load_document(st.session_state.input_text)
    
    # Text input area
    st.header("📝 Input Document")
    
    input_text = st.text_area(
        "Enter your document text here:",
        height=200,
        placeholder="Paste your markdown or text content here...",
        key="input_text"
    )
    
    if input_text:
        # Process the document
        st.session_state.viewer.load_document(input_text)
        
        # Load JSON data if available
        if hasattr(st.session_state, 'json_data') and st.session_state.json_data:
            st.session_state.viewer.load_json_data(st.session_state.json_data)
            
            # Show JSON analysis
            st.header("📊 JSON Data Analysis")
            analysis = st.session_state.viewer.analyze_json_structure()
            
            if analysis:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Items", analysis['total_items'])
                with col2:
                    st.metric("Text Items", analysis['types'].get('text', 0))
                with col3:
                    st.metric("Images", analysis['types'].get('image', 0))
                with col4:
                    st.metric("Tables", analysis['types'].get('table', 0))
                    
                # Show pages distribution
                if analysis['pages']:
                    st.markdown(f"**Pages:** {', '.join(map(str, analysis['pages']))}")
        
        # Display statistics
        st.header("📊 Chunking Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Original Length", f"{len(input_text):,} chars")
        with col2:
            st.metric("Number of Chunks", len(st.session_state.viewer.chunks))
        with col3:
            avg_chunk_size = sum(len(chunk.content) for chunk in st.session_state.viewer.chunks) / len(st.session_state.viewer.chunks) if st.session_state.viewer.chunks else 0
            st.metric("Avg Chunk Size", f"{avg_chunk_size:.0f} chars")
        with col4:
            st.metric("Max Chunk Size", max(len(chunk.content) for chunk in st.session_state.viewer.chunks) if st.session_state.viewer.chunks else 0)
        
        # Main content area with two columns
        st.header("📄 Document Comparison")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎯 Original Document with Chunk Boundaries")
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
            st.subheader("🧩 Individual Chunks")
            
            # Create a container for chunks with scroll
            chunks_container = st.container()
            
            with chunks_container:
                chunks_html = ""
                for i, chunk in enumerate(st.session_state.viewer.chunks):
                    chunk_color = st.session_state.viewer._get_chunk_color(i)
                    
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
                            Chunk {i+1} ({len(chunk.content)} chars)
                            <span style="color: #666; font-weight: normal; font-size: 12px;">
                                | Pos: {chunk.start_pos}-{chunk.end_pos}
                            </span>
                        </div>
                        <div style="
                            font-family: monospace;
                            font-size: 13px;
                            line-height: 1.4;
                            white-space: pre-wrap;
                            max-height: 150px;
                            overflow-y: auto;
                        ">
                            {chunk.content}
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
        
        with st.expander("View Chunk Details", expanded=False):
            for i, chunk in enumerate(st.session_state.viewer.chunks):
                st.markdown(f"**Chunk {i+1}**")
                st.markdown(f"- **Length:** {len(chunk.content)} characters")
                st.markdown(f"- **Position:** {chunk.start_pos} - {chunk.end_pos}")
                st.markdown(f"- **Content Preview:** {chunk.content[:100]}...")
                st.markdown("---")
    
    else:
        st.info("👆 Please enter some text above to see the chunking visualization")
        
        # Show example
        st.markdown("### 💡 Example Usage")
        st.markdown("""
        This tool helps you understand how the document chunking process works in the RAG system:
        
        1. **Enter or load** your document text
        2. **Adjust** chunk size and overlap parameters
        3. **Visualize** how the text is split into chunks
        4. **Compare** the original document with highlighted boundaries and individual chunks
        
        The left column shows the original document with colored boundaries indicating where each chunk starts and ends.
        The right column shows each chunk individually with metadata.
        """)


if __name__ == "__main__":
    main()