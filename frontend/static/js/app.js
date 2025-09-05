// Main application JavaScript
class ChunkViewer {
    constructor() {
        this.documentData = null;
        this.chunksData = [];
        this.currentFilter = 'text';
        this.colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
        ];
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.hideMainContent();
    }
    
    bindEvents() {
        // Load button
        document.getElementById('loadBtn').addEventListener('click', () => {
            this.loadData();
        });
        
        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.refreshData();
        });
        
        // Filter buttons
        document.getElementById('filterText').addEventListener('click', () => {
            this.setFilter('text');
        });
        
        document.getElementById('filterImages').addEventListener('click', () => {
            this.setFilter('image');
        });
        
        document.getElementById('filterTables').addEventListener('click', () => {
            this.setFilter('table');
        });
        
        // Scroll to top
        document.getElementById('scrollToTop').addEventListener('click', () => {
            this.scrollToTop();
        });
        
        // Modal close
        document.getElementById('closeModal').addEventListener('click', () => {
            this.closeModal();
        });
        
        // Close modal on background click
        document.getElementById('chunkModal').addEventListener('click', (e) => {
            if (e.target === document.getElementById('chunkModal')) {
                this.closeModal();
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }
    
    async loadData() {
        const markdownPath = document.getElementById('markdownPath').value;
        
        if (!markdownPath.trim()) {
            this.showError('Please enter a markdown file path');
            return;
        }
        
        this.showLoading();
        this.hideError();
        
        try {
            const response = await fetch('/api/load', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    markdown_path: markdownPath
                })
            });
            
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || 'Failed to load data');
            }
            
            // Update statistics
            this.updateStats(result.stats);
            
            // Load document and chunks data
            await this.loadDocumentAndChunks();
            
            this.hideLoading();
            this.showMainContent();
            
        } catch (error) {
            this.hideLoading();
            this.showError(`Error loading data: ${error.message}`);
        }
    }
    
    async loadDocumentAndChunks() {
        try {
            // Load document data
            const docResponse = await fetch('/api/document');
            this.documentData = await docResponse.json();
            
            // Load chunks data
            const chunksResponse = await fetch('/api/chunks');
            this.chunksData = await chunksResponse.json();
            
            // Render both panels
            this.renderDocument();
            this.renderChunks();
            
            // Set up synchronized scrolling
            this.setupSynchronizedScrolling();
            
        } catch (error) {
            throw new Error(`Failed to load document and chunks: ${error.message}`);
        }
    }
    
    renderDocument() {
        const panel = document.getElementById('documentPanel');
        
        if (!this.documentData || !this.documentData.segments) {
            panel.innerHTML = '<p>No document data available</p>';
            return;
        }
        
        let html = '';
        
        this.documentData.segments.forEach((segment, index) => {
            if (segment.type === 'text') {
                html += `<span class="document-text">${this.escapeHtml(segment.content)}</span>`;
            } else if (segment.type === 'chunk') {
                const colorIndex = segment.chunk_index % this.colors.length;
                const confidence = this.getConfidenceIcon(segment.match_score);
                
                html += `
                    <div class="chunk-highlight chunk-color-${colorIndex}" 
                         data-chunk-index="${segment.chunk_index}"
                         onclick="chunkViewer.showChunkDetails(${segment.chunk_index})">
                        <div class="chunk-header chunk-header-${colorIndex}">
                            Chunk ${segment.chunk_index + 1} (${segment.chunk_type}) ${confidence}
                            <small>ID: ${segment.chunk_id} | Page: ${segment.page_idx}</small>
                        </div>
                        <div class="chunk-content">${this.escapeHtml(segment.content)}</div>
                    </div>
                `;
            }
        });
        
        panel.innerHTML = html;
    }
    
    renderChunks() {
        const panel = document.getElementById('chunksPanel');
        
        if (!this.chunksData.length) {
            panel.innerHTML = '<p>No chunks data available</p>';
            return;
        }
        
        // Filter chunks based on current filter
        const filteredChunks = this.chunksData.filter(chunk => {
            if (this.currentFilter === 'text') return chunk.chunk_type === 'text';
            if (this.currentFilter === 'image') return chunk.chunk_type === 'image';
            if (this.currentFilter === 'table') return chunk.chunk_type === 'table';
            return true;
        });
        
        let html = '';
        
        filteredChunks.forEach((chunk, displayIndex) => {
            const colorIndex = chunk.index % this.colors.length;
            const confidence = this.getConfidenceIcon(chunk.match_score);
            const position = chunk.start_pos >= 0 ? 
                `${chunk.start_pos}-${chunk.end_pos}` : 
                'Not mapped';
            
            const preview = chunk.content.length > 200 ? 
                chunk.content.substring(0, 200) + '...' : 
                chunk.content;
            
            html += `
                <div class="chunk-item chunk-color-${colorIndex}" 
                     data-chunk-index="${chunk.index}"
                     onclick="chunkViewer.showChunkDetails(${chunk.index})">
                    <div class="confidence-indicator">${confidence}</div>
                    <div class="chunk-item-header chunk-header-${colorIndex}">
                        Chunk ${chunk.index + 1} (${chunk.chunk_type})
                    </div>
                    <div class="chunk-meta">
                        ID: ${chunk.chunk_id} | Page: ${chunk.page_idx} | 
                        Position: ${position} | 
                        Length: ${chunk.content.length} chars
                    </div>
                    <div class="chunk-preview">${this.escapeHtml(preview)}</div>
                </div>
            `;
        });
        
        panel.innerHTML = html;
    }
    
    showChunkDetails(chunkIndex) {
        const chunk = this.chunksData.find(c => c.index === chunkIndex);
        if (!chunk) return;
        
        // Populate modal
        document.getElementById('modalTitle').textContent = `Chunk ${chunk.index + 1} Details`;
        document.getElementById('modalChunkId').textContent = chunk.chunk_id;
        document.getElementById('modalChunkType').textContent = chunk.chunk_type;
        document.getElementById('modalPageIdx').textContent = chunk.page_idx;
        
        const position = chunk.start_pos >= 0 ? 
            `${chunk.start_pos} - ${chunk.end_pos}` : 
            'Not mapped to document';
        document.getElementById('modalPosition').textContent = position;
        
        const scoreText = `${chunk.match_score.toFixed(2)} ${this.getConfidenceIcon(chunk.match_score)}`;
        document.getElementById('modalMatchScore').innerHTML = scoreText;
        
        // Handle path (only show if exists)
        const pathContainer = document.getElementById('modalPathContainer');
        if (chunk.path) {
            pathContainer.style.display = 'block';
            document.getElementById('modalPath').textContent = chunk.path;
        } else {
            pathContainer.style.display = 'none';
        }
        
        document.getElementById('modalContent').textContent = chunk.content;
        
        // Show modal
        document.getElementById('chunkModal').classList.remove('hidden');
    }
    
    closeModal() {
        document.getElementById('chunkModal').classList.add('hidden');
    }
    
    setFilter(filterType) {
        this.currentFilter = filterType;
        
        // Update filter buttons
        document.querySelectorAll('.panel-controls .btn').forEach(btn => {
            btn.classList.remove('filter-active');
        });
        
        document.getElementById(`filter${filterType.charAt(0).toUpperCase() + filterType.slice(1)}`).classList.add('filter-active');
        
        // Re-render chunks
        this.renderChunks();
    }
    
    setupSynchronizedScrolling() {
        const documentPanel = document.getElementById('documentPanel');
        const chunksPanel = document.getElementById('chunksPanel');
        
        let isScrolling = false;
        
        documentPanel.addEventListener('scroll', () => {
            if (isScrolling) return;
            isScrolling = true;
            
            const scrollPercentage = documentPanel.scrollTop / 
                (documentPanel.scrollHeight - documentPanel.clientHeight);
            
            chunksPanel.scrollTop = scrollPercentage * 
                (chunksPanel.scrollHeight - chunksPanel.clientHeight);
            
            setTimeout(() => {
                isScrolling = false;
            }, 50);
        });
        
        chunksPanel.addEventListener('scroll', () => {
            if (isScrolling) return;
            isScrolling = true;
            
            const scrollPercentage = chunksPanel.scrollTop / 
                (chunksPanel.scrollHeight - chunksPanel.clientHeight);
            
            documentPanel.scrollTop = scrollPercentage * 
                (documentPanel.scrollHeight - documentPanel.clientHeight);
            
            setTimeout(() => {
                isScrolling = false;
            }, 50);
        });
    }
    
    scrollToTop() {
        document.getElementById('documentPanel').scrollTop = 0;
        document.getElementById('chunksPanel').scrollTop = 0;
    }
    
    refreshData() {
        this.hideMainContent();
        this.hideError();
        this.loadData();
    }
    
    updateStats(stats) {
        document.getElementById('docLength').textContent = `${stats.document_length.toLocaleString()} chars`;
        document.getElementById('totalChunks').textContent = stats.total_chunks;
        document.getElementById('textChunks').textContent = stats.text_chunks;
        document.getElementById('mappedChunks').textContent = stats.mapped_chunks;
        document.getElementById('unmappedChunks').textContent = stats.unmapped_chunks;
        
        document.getElementById('stats').classList.remove('hidden');
    }
    
    showLoading() {
        document.getElementById('loading').classList.remove('hidden');
    }
    
    hideLoading() {
        document.getElementById('loading').classList.add('hidden');
    }
    
    showError(message) {
        document.getElementById('errorText').textContent = message;
        document.getElementById('error').classList.remove('hidden');
    }
    
    hideError() {
        document.getElementById('error').classList.add('hidden');
    }
    
    showMainContent() {
        document.getElementById('mainContent').classList.remove('hidden');
    }
    
    hideMainContent() {
        document.getElementById('mainContent').classList.add('hidden');
        document.getElementById('stats').classList.add('hidden');
    }
    
    getConfidenceIcon(score) {
        if (score >= 1.0) return '✅';      // Perfect match
        if (score >= 0.8) return '🟡';     // Good match
        if (score >= 0.6) return '🟠';     // Partial match
        return '❌';                        // No match
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the application when the page loads
let chunkViewer;

document.addEventListener('DOMContentLoaded', () => {
    chunkViewer = new ChunkViewer();
});