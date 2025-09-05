// Main Application State
const app = {
    currentDocument: '',
    currentChunks: [],
    currentCollection: '',
    selectedChunkId: null,
    highlightedText: new Set()
};

// DOM Elements
const elements = {
    collectionSelect: document.getElementById('collection-select'),
    searchInput: document.getElementById('search-input'),
    searchBtn: document.getElementById('search-btn'),
    refreshBtn: document.getElementById('refresh-btn'),
    clearHighlightsBtn: document.getElementById('clear-highlights-btn'),
    documentContainer: document.getElementById('document-container'),
    documentPath: document.getElementById('document-path'),
    chunksContainer: document.getElementById('chunks-container'),
    chunkCount: document.getElementById('chunk-count'),
    statusMessage: document.getElementById('status-message'),
    modal: document.getElementById('chunk-detail-modal'),
    modalBody: document.getElementById('modal-body'),
    modalTitle: document.getElementById('modal-title'),
    modalClose: document.querySelector('.modal-close')
};

// Initialize Application
async function init() {
    updateStatus('Initializing...');
    
    // Load collections
    await loadCollections();
    
    // Load document
    await loadDocument();
    
    // Setup event listeners
    setupEventListeners();
    
    updateStatus('Ready');
}

// Load available collections
async function loadCollections() {
    try {
        const response = await fetch('/api/collections');
        const data = await response.json();
        
        if (data.success) {
            elements.collectionSelect.innerHTML = '<option value="">Select a collection...</option>';
            data.collections.forEach(collection => {
                const option = document.createElement('option');
                option.value = collection;
                option.textContent = collection;
                elements.collectionSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load collections:', error);
        updateStatus('Error loading collections');
    }
}

// Load original document
async function loadDocument() {
    try {
        updateStatus('Loading document...');
        const response = await fetch('/api/document');
        const data = await response.json();
        
        if (data.success) {
            app.currentDocument = data.content;
            elements.documentPath.textContent = data.path;
            renderDocument(data.content);
            updateStatus('Document loaded');
        } else {
            elements.documentContainer.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            updateStatus('Document load failed');
        }
    } catch (error) {
        console.error('Failed to load document:', error);
        elements.documentContainer.innerHTML = '<div class="error">Failed to load document</div>';
        updateStatus('Document load error');
    }
}

// Render markdown document
function renderDocument(content) {
    // Parse markdown to HTML
    const html = marked.parse(content);
    elements.documentContainer.innerHTML = html;
    
    // Add line numbers for better reference
    addLineReferences();
}

// Add line references to document
function addLineReferences() {
    const lines = app.currentDocument.split('\n');
    let currentPos = 0;
    
    // Store position mappings for highlighting
    app.linePositions = lines.map((line, index) => {
        const start = currentPos;
        currentPos += line.length + 1; // +1 for newline
        return { line: index + 1, start, end: currentPos - 1, text: line };
    });
}

// Load chunks for selected collection
async function loadChunks(collection) {
    if (!collection) {
        elements.chunksContainer.innerHTML = '<div class="loading">Select a collection to view chunks</div>';
        elements.chunkCount.textContent = '0 chunks';
        return;
    }
    
    try {
        updateStatus(`Loading chunks from ${collection}...`);
        elements.chunksContainer.innerHTML = '<div class="loading">Loading chunks...</div>';
        
        const response = await fetch(`/api/chunks/${collection}`);
        const data = await response.json();
        
        if (data.success) {
            app.currentChunks = data.chunks;
            app.currentCollection = collection;
            renderChunks(data.chunks);
            elements.chunkCount.textContent = `${data.count} chunks`;
            updateStatus(`Loaded ${data.count} chunks`);
        } else {
            elements.chunksContainer.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            updateStatus('Chunk load failed');
        }
    } catch (error) {
        console.error('Failed to load chunks:', error);
        elements.chunksContainer.innerHTML = '<div class="error">Failed to load chunks</div>';
        updateStatus('Chunk load error');
    }
}

// Render chunks in the panel
function renderChunks(chunks) {
    if (chunks.length === 0) {
        elements.chunksContainer.innerHTML = '<div class="no-data">No chunks found</div>';
        return;
    }
    
    elements.chunksContainer.innerHTML = '';
    
    chunks.forEach(chunk => {
        const chunkElement = createChunkElement(chunk);
        elements.chunksContainer.appendChild(chunkElement);
    });
}

// Create chunk element
function createChunkElement(chunk) {
    const div = document.createElement('div');
    div.className = 'chunk-item';
    div.dataset.chunkId = chunk.id;
    
    const metadata = chunk.metadata || {};
    const chunkType = metadata.type || 'unknown';
    const pageIdx = metadata.page_idx !== undefined ? metadata.page_idx : '?';
    
    // Extract chunk text (first part of document for display)
    const chunkText = chunk.document ? chunk.document.substring(0, 200) : 'No content';
    
    div.innerHTML = `
        <div class="chunk-header">
            <span class="chunk-id">${chunk.id}</span>
            <span class="chunk-type ${chunkType}">${chunkType}</span>
        </div>
        <div class="chunk-content">${escapeHtml(chunkText)}${chunkText.length > 200 ? '...' : ''}</div>
        <div class="chunk-metadata">
            <span>Page: ${pageIdx}</span>
            ${metadata.path ? `<span>Path: ${metadata.path}</span>` : ''}
        </div>
    `;
    
    // Add click handler
    div.addEventListener('click', () => selectChunk(chunk));
    
    return div;
}

// Select and highlight chunk
function selectChunk(chunk) {
    // Check if this chunk is already selected
    if (app.selectedChunkId === chunk.id) {
        // Second click on the same chunk - show detailed modal
        showChunkDetailsModal(chunk);
        return;
    }
    
    // Remove previous selection
    document.querySelectorAll('.chunk-item.active').forEach(el => {
        el.classList.remove('active');
    });
    
    // Add active class to selected chunk
    const chunkElement = document.querySelector(`[data-chunk-id="${chunk.id}"]`);
    if (chunkElement) {
        chunkElement.classList.add('active');
        chunkElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    app.selectedChunkId = chunk.id;
    
    // Highlight in document with details
    highlightChunkInDocument(chunk);
    updateStatus(`Chunk ${chunk.id} selected. Click again to see full details.`);
}

// Highlight chunk text in document with sidebar indicator
function highlightChunkInDocument(chunk) {
    // Clear previous highlights
    clearHighlights();
    
    const chunkText = chunk.document;
    const metadata = chunk.metadata || {};
    if (!chunkText) return;
    
    // Try to find exact match first
    const searchText = chunkText.substring(0, Math.min(100, chunkText.length));
    
    // Get all text content from the document
    const documentText = elements.documentContainer.textContent;
    const index = documentText.indexOf(searchText);
    
    if (index !== -1) {
        // Find the element containing the text
        const elements_list = elements.documentContainer.querySelectorAll('*');
        let targetElement = null;
        
        for (let elem of elements_list) {
            if (elem.children.length === 0 && elem.textContent.includes(searchText)) {
                targetElement = elem;
                break;
            }
        }
        
        if (!targetElement) {
            // Try to find parent element containing the text
            for (let elem of elements_list) {
                if (elem.textContent.includes(searchText)) {
                    targetElement = elem;
                    break;
                }
            }
        }
        
        if (targetElement) {
            // Add a sidebar indicator instead of modifying the text
            targetElement.classList.add('chunk-highlighted');
            targetElement.dataset.chunkId = chunk.id;
            targetElement.dataset.chunkType = metadata.type || 'unknown';
            targetElement.dataset.chunkPage = metadata.page_idx || 'N/A';
            
            // Create sidebar indicator
            const indicator = document.createElement('div');
            indicator.className = 'chunk-indicator';
            indicator.innerHTML = `
                <div class="indicator-line"></div>
                <div class="indicator-info">
                    <strong>${chunk.id}</strong>
                    <span class="chunk-type ${metadata.type || 'unknown'}">${metadata.type || 'unknown'}</span>
                    <span>Page: ${metadata.page_idx || 'N/A'}</span>
                </div>
            `;
            
            // Position the indicator
            targetElement.style.position = 'relative';
            targetElement.appendChild(indicator);
            
            // Scroll to the highlighted element
            targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            updateStatus(`Chunk ${chunk.id} highlighted`);
        } else {
            updateStatus(`Could not locate element for chunk`);
        }
    } else {
        updateStatus(`Chunk text not found in document (may be in an image or table)`);
    }
}

// Clear all highlights
function clearHighlights() {
    // Remove chunk indicators
    const indicators = elements.documentContainer.querySelectorAll('.chunk-indicator');
    indicators.forEach(indicator => indicator.remove());
    
    // Remove highlight classes
    const highlighted = elements.documentContainer.querySelectorAll('.chunk-highlighted');
    highlighted.forEach(elem => {
        elem.classList.remove('chunk-highlighted');
        elem.style.position = '';
        delete elem.dataset.chunkId;
        delete elem.dataset.chunkType;
        delete elem.dataset.chunkPage;
    });
}

// Removed - no longer using modal for chunk details

// Search chunks
async function searchChunks() {
    const query = elements.searchInput.value.trim();
    if (!query || !app.currentCollection) return;
    
    try {
        updateStatus(`Searching for "${query}"...`);
        const response = await fetch(`/api/search/${app.currentCollection}?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success) {
            renderChunks(data.chunks);
            elements.chunkCount.textContent = `${data.count} matches`;
            updateStatus(`Found ${data.count} matches`);
        }
    } catch (error) {
        console.error('Search failed:', error);
        updateStatus('Search failed');
    }
}

// Setup event listeners
function setupEventListeners() {
    // Collection selection
    elements.collectionSelect.addEventListener('change', (e) => {
        loadChunks(e.target.value);
    });
    
    // Search
    elements.searchBtn.addEventListener('click', searchChunks);
    elements.searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchChunks();
    });
    
    // Refresh
    elements.refreshBtn.addEventListener('click', () => {
        if (app.currentCollection) {
            loadChunks(app.currentCollection);
        }
        loadDocument();
    });
    
    // Clear highlights
    elements.clearHighlightsBtn.addEventListener('click', clearHighlights);
    
    // Modal close events
    elements.modalClose.addEventListener('click', closeModal);
    elements.modal.addEventListener('click', (e) => {
        if (e.target === elements.modal) {
            closeModal();
        }
    });
    
    // Escape key to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && elements.modal.classList.contains('show')) {
            closeModal();
        }
    });
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateStatus(message) {
    elements.statusMessage.textContent = message;
}

// Show chunk details modal
function showChunkDetailsModal(chunk) {
    const metadata = chunk.metadata || {};
    
    // Set modal title
    elements.modalTitle.textContent = `Chunk Details: ${chunk.id}`;
    
    // Build detailed content HTML
    let contentHTML = `
        <div class="chunk-detail-section">
            <h4>Chunk Information</h4>
            <div class="chunk-info-grid">
                <div class="info-item">
                    <span class="info-label">ID:</span>
                    <span class="info-value">${chunk.id}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Type:</span>
                    <span class="info-value"><span class="chunk-type ${metadata.type || 'unknown'}">${metadata.type || 'unknown'}</span></span>
                </div>
                <div class="info-item">
                    <span class="info-label">Page Index:</span>
                    <span class="info-value">${metadata.page_idx !== undefined ? metadata.page_idx : 'N/A'}</span>
                </div>
                ${metadata.path ? `
                <div class="info-item">
                    <span class="info-label">Path:</span>
                    <span class="info-value">${metadata.path}</span>
                </div>
                ` : ''}
            </div>
        </div>
    `;
    
    // Add summary if exists
    if (metadata.summary) {
        contentHTML += `
            <div class="chunk-detail-section">
                <h4>Summary</h4>
                <div class="chunk-summary">
                    ${escapeHtml(metadata.summary)}
                </div>
            </div>
        `;
    }
    
    // Add full content
    contentHTML += `
        <div class="chunk-detail-section">
            <h4>Full Content</h4>
            <div class="chunk-full-content">
                <pre>${escapeHtml(chunk.document || 'No content available')}</pre>
            </div>
        </div>
    `;
    
    // Set modal content
    elements.modalBody.innerHTML = contentHTML;
    
    // Show modal
    elements.modal.classList.add('show');
    updateStatus('Viewing chunk details');
}

// Close modal
function closeModal() {
    elements.modal.classList.remove('show');
    updateStatus('Ready');
}

// Style additions for chunk sidebar indicators
const style = document.createElement('style');
style.textContent = `
    .chunk-highlighted {
        position: relative;
        background: linear-gradient(to right, transparent 0%, rgba(255, 235, 59, 0.1) 2%, rgba(255, 235, 59, 0.1) 98%, transparent 100%);
        transition: background 0.3s;
    }
    
    .chunk-highlighted:hover {
        background: linear-gradient(to right, transparent 0%, rgba(255, 235, 59, 0.2) 2%, rgba(255, 235, 59, 0.2) 98%, transparent 100%);
    }
    
    .chunk-indicator {
        position: absolute;
        left: -60px;
        top: 0;
        height: 100%;
        width: 50px;
        display: flex;
        align-items: center;
        pointer-events: none;
    }
    
    .indicator-line {
        position: absolute;
        left: 45px;
        top: 0;
        bottom: 0;
        width: 4px;
        background: #333;
        border-radius: 2px;
    }
    
    .indicator-info {
        position: absolute;
        left: -200px;
        top: 50%;
        transform: translateY(-50%);
        background: white;
        border: 2px solid #333;
        border-radius: 4px;
        padding: 0.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        white-space: nowrap;
        font-size: 0.75rem;
        opacity: 0;
        transition: opacity 0.2s;
        pointer-events: auto;
    }
    
    .chunk-indicator:hover .indicator-info,
    .chunk-highlighted:hover .indicator-info {
        opacity: 1;
    }
    
    .indicator-info strong {
        display: block;
        font-size: 0.8rem;
        color: #333;
        margin-bottom: 0.25rem;
    }
    
    .indicator-info span {
        display: block;
        margin: 0.15rem 0;
        color: #666;
    }
    
    .indicator-info .chunk-type {
        display: inline-block;
        padding: 0.1rem 0.3rem;
        border-radius: 2px;
        font-size: 0.7rem;
        margin-bottom: 0.2rem;
    }
    
    #document-container {
        position: relative;
        padding-left: 70px;
    }
    
    .error {
        color: #d32f2f;
        padding: 1rem;
        text-align: center;
    }
    
    .no-data {
        color: #999;
        padding: 2rem;
        text-align: center;
    }
`;

// Start the application
document.addEventListener('DOMContentLoaded', init);