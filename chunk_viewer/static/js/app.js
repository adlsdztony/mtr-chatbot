// Configure PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

// Main Application State
const app = {
    currentChunks: [],
    selectedChunkId: null,
    pdfDoc: null,
    scale: 1.0,
    pageCanvases: [],
    pageHeights: [],
    fitWidth: true, // Default to fit width
    isRendering: false,
    renderedPages: new Set(),
    pageObserver: null,
    availableFiles: [],
    currentFilename: null
};

// DOM Elements
const elements = {
    documentPath: document.getElementById('document-path'),
    chunksContainer: document.getElementById('chunks-container'),
    chunkCount: document.getElementById('chunk-count'),
    fileSelector: document.getElementById('file-selector'),
    modal: document.getElementById('chunk-detail-modal'),
    modalBody: document.getElementById('modal-body'),
    modalTitle: document.getElementById('modal-title'),
    modalClose: document.querySelector('.modal-close'),
    pdfViewer: document.getElementById('pdf-viewer'),
    pdfPagesContainer: document.getElementById('pdf-pages-container'),
    pdfLoading: document.getElementById('pdf-loading'),
    zoomIn: document.getElementById('zoom-in'),
    zoomOut: document.getElementById('zoom-out'),
    zoomLevel: document.getElementById('zoom-level'),
    fitWidth: document.getElementById('fit-width')
};

// Initialize Application
async function init() {
    // Setup event listeners
    setupEventListeners();
    
    // Load available files first
    await loadAvailableFiles();
    
    // If files are available, load the first one
    if (app.availableFiles.length > 0) {
        app.currentFilename = app.availableFiles[0];
        elements.fileSelector.value = app.currentFilename;
        await loadPDF();
        await loadChunks();
    } else {
        elements.chunksContainer.innerHTML = '<div class="no-data">No documents found in database</div>';
    }
}

// Load PDF document
async function loadPDF() {
    const pdfUrl = `/api/pdf?filename=${encodeURIComponent(app.currentFilename || 'manual')}`;
    
    try {
        elements.pdfLoading.style.display = 'block';
        elements.pdfPagesContainer.style.display = 'none';
        
        // Load the PDF document
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        app.pdfDoc = await loadingTask.promise;
        
        // Setup lazy loading
        await setupLazyLoading();
        
        elements.pdfLoading.style.display = 'none';
        elements.pdfPagesContainer.style.display = 'block';
        
    } catch (error) {
        console.error('Error loading PDF:', error);
        elements.pdfLoading.textContent = `Error loading PDF for ${app.currentFilename}: ${error.message}`;
    }
}

// Setup lazy loading for PDF pages
async function setupLazyLoading() {
    if (app.isRendering) return;
    app.isRendering = true;
    
    // Clear existing pages
    elements.pdfPagesContainer.innerHTML = '';
    app.pageCanvases = [];
    app.pageHeights = [];
    app.renderedPages.clear();
    
    // Calculate scale for fit-width
    if (app.fitWidth && app.pdfDoc.numPages > 0) {
        const page = await app.pdfDoc.getPage(1);
        const viewport = page.getViewport({ scale: 1.0 });
        const containerWidth = elements.pdfViewer.clientWidth - 40; // Subtract padding
        app.scale = containerWidth / viewport.width;
        elements.zoomLevel.textContent = Math.round(app.scale * 100) + '%';
    }
    
    // Create placeholders for all pages
    for (let pageNum = 1; pageNum <= app.pdfDoc.numPages; pageNum++) {
        // Create page container
        const pageContainer = document.createElement('div');
        pageContainer.className = 'pdf-page-container';
        pageContainer.dataset.pageNum = pageNum;
        
        // Add page number label (starting from 0)
        const pageLabel = document.createElement('div');
        pageLabel.className = 'page-label';
        pageLabel.textContent = `Page ${pageNum - 1}`; // Start from 0
        pageContainer.appendChild(pageLabel);
        
        // Create canvas placeholder
        const canvas = document.createElement('canvas');
        canvas.className = 'pdf-page';
        canvas.style.display = 'none'; // Hide initially
        pageContainer.appendChild(canvas);
        
        // Create loading placeholder
        const placeholder = document.createElement('div');
        placeholder.className = 'pdf-page-placeholder';
        placeholder.style.height = '1000px'; // Default height
        placeholder.style.background = '#f0f0f0';
        placeholder.style.display = 'flex';
        placeholder.style.alignItems = 'center';
        placeholder.style.justifyContent = 'center';
        placeholder.innerHTML = '<span style="color: #999;">Loading...</span>';
        pageContainer.appendChild(placeholder);
        
        elements.pdfPagesContainer.appendChild(pageContainer);
        app.pageCanvases.push(canvas);
    }
    
    app.isRendering = false;
    
    // Setup intersection observer for lazy loading
    setupIntersectionObserver();
    
    // Render first few pages immediately
    for (let i = 1; i <= Math.min(3, app.pdfDoc.numPages); i++) {
        await renderPage(i);
    }
}

// Setup intersection observer for lazy loading
function setupIntersectionObserver() {
    if (app.pageObserver) {
        app.pageObserver.disconnect();
    }
    
    const options = {
        root: elements.pdfViewer,
        rootMargin: '500px',
        threshold: 0
    };
    
    app.pageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const pageNum = parseInt(entry.target.dataset.pageNum);
                if (!app.renderedPages.has(pageNum)) {
                    renderPage(pageNum);
                }
            }
        });
    }, options);
    
    // Observe all page containers
    const pageContainers = elements.pdfPagesContainer.querySelectorAll('.pdf-page-container');
    pageContainers.forEach(container => {
        app.pageObserver.observe(container);
    });
}

// Render a specific page
async function renderPage(pageNum) {
    if (app.renderedPages.has(pageNum)) return;
    app.renderedPages.add(pageNum);
    
    try {
        const page = await app.pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: app.scale });
        
        const canvas = app.pageCanvases[pageNum - 1];
        const pageContainer = canvas.parentElement;
        const placeholder = pageContainer.querySelector('.pdf-page-placeholder');
        
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        
        // Store page height for scroll calculations
        app.pageHeights[pageNum - 1] = viewport.height;
        
        const ctx = canvas.getContext('2d');
        const renderContext = {
            canvasContext: ctx,
            viewport: viewport
        };
        
        await page.render(renderContext).promise;
        
        // Show canvas and hide placeholder
        canvas.style.display = 'block';
        if (placeholder) {
            placeholder.style.display = 'none';
        }
    } catch (error) {
        console.error(`Error rendering page ${pageNum}:`, error);
    }
}

// Re-render all visible pages (for zoom changes)
async function rerenderAllPages() {
    if (app.isRendering) return;
    app.isRendering = true;
    
    // Clear rendered pages set
    app.renderedPages.clear();
    
    // Calculate new scale
    if (app.fitWidth && app.pdfDoc.numPages > 0) {
        const page = await app.pdfDoc.getPage(1);
        const viewport = page.getViewport({ scale: 1.0 });
        const containerWidth = elements.pdfViewer.clientWidth - 40;
        app.scale = containerWidth / viewport.width;
        elements.zoomLevel.textContent = Math.round(app.scale * 100) + '%';
    }
    
    // Reset all pages to placeholders
    const pageContainers = elements.pdfPagesContainer.querySelectorAll('.pdf-page-container');
    pageContainers.forEach((container, index) => {
        const canvas = app.pageCanvases[index];
        const placeholder = container.querySelector('.pdf-page-placeholder');
        
        canvas.style.display = 'none';
        if (placeholder) {
            placeholder.style.display = 'flex';
        }
    });
    
    app.isRendering = false;
    
    // Re-render visible pages
    const visibleContainers = Array.from(pageContainers).filter(container => {
        const rect = container.getBoundingClientRect();
        const viewerRect = elements.pdfViewer.getBoundingClientRect();
        return rect.bottom > viewerRect.top && rect.top < viewerRect.bottom;
    });
    
    for (const container of visibleContainers) {
        const pageNum = parseInt(container.dataset.pageNum);
        await renderPage(pageNum);
    }
}

// Navigate to specific PDF page
function navigateToPdfPage(pageNumber) {
    if (!app.pdfDoc || pageNumber < 1 || pageNumber > app.pdfDoc.numPages) return;
    
    const pageContainer = document.querySelector(`[data-page-num="${pageNumber}"]`);
    if (pageContainer) {
        pageContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Ensure the page is rendered
        if (!app.renderedPages.has(pageNumber)) {
            renderPage(pageNumber);
        }
    }
}

// Zoom in
async function onZoomIn() {
    app.fitWidth = false;
    app.scale = Math.min(app.scale * 1.2, 3.0);
    elements.zoomLevel.textContent = Math.round(app.scale * 100) + '%';
    await rerenderAllPages();
}

// Zoom out
async function onZoomOut() {
    app.fitWidth = false;
    app.scale = Math.max(app.scale / 1.2, 0.5);
    elements.zoomLevel.textContent = Math.round(app.scale * 100) + '%';
    await rerenderAllPages();
}

// Fit to width
async function onFitWidth() {
    app.fitWidth = true;
    await rerenderAllPages();
}

// Load available files from database
async function loadAvailableFiles() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();
        
        if (data.success) {
            app.availableFiles = data.files;
            
            // Populate file selector
            elements.fileSelector.innerHTML = '';
            
            if (app.availableFiles.length === 0) {
                elements.fileSelector.innerHTML = '<option value="">No files available</option>';
            } else {
                app.availableFiles.forEach(filename => {
                    const option = document.createElement('option');
                    option.value = filename;
                    option.textContent = filename;
                    elements.fileSelector.appendChild(option);
                });
            }
        } else {
            console.error('Failed to load available files:', data.error);
            elements.fileSelector.innerHTML = '<option value="">Error loading files</option>';
        }
    } catch (error) {
        console.error('Failed to fetch available files:', error);
        elements.fileSelector.innerHTML = '<option value="">Error loading files</option>';
    }
}

// Load chunks from both collections for selected file
async function loadChunks() {
    if (!app.currentFilename) {
        elements.chunksContainer.innerHTML = '<div class="no-data">Please select a file</div>';
        return;
    }
    
    try {
        elements.chunksContainer.innerHTML = '<div class="loading">Loading chunks...</div>';
        
        const response = await fetch(`/api/chunks?filename=${encodeURIComponent(app.currentFilename)}`);
        const data = await response.json();
        
        if (data.success) {
            app.currentChunks = data.chunks;
            renderChunks(data.chunks);
            elements.chunkCount.textContent = `${data.count} chunks`;
        } else {
            elements.chunksContainer.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            app.currentChunks = [];
        }
    } catch (error) {
        console.error('Failed to load chunks:', error);
        elements.chunksContainer.innerHTML = '<div class="error">Failed to load chunks</div>';
        app.currentChunks = [];
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
    const source = chunk.source || 'unknown';
    const filename = metadata.filename || 'unknown';
    
    // Extract chunk text (first part of document for display)
    const chunkText = chunk.document ? chunk.document.substring(0, 200) : 'No content';
    
    div.innerHTML = `
        <div class="chunk-header">
            <span class="chunk-id">${chunk.id}</span>
            <span class="chunk-type ${chunkType}">${chunkType}</span>
        </div>
        <div class="chunk-content">${escapeHtml(chunkText)}${chunkText.length > 200 ? '...' : ''}</div>
        <div class="chunk-metadata">
            <span>File: ${filename}</span>
            <span>Page: ${pageIdx}</span>
            <span>Source: ${source}</span>
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
    }
    
    app.selectedChunkId = chunk.id;
    
    // Jump to page in PDF
    const metadata = chunk.metadata || {};
    if (metadata.page_idx !== undefined) {
        // Convert 0-based page_idx to 1-based PDF page number
        const pdfPageNumber = metadata.page_idx + 1;
        navigateToPdfPage(pdfPageNumber);
    }
}

// Setup event listeners
function setupEventListeners() {
    // PDF controls
    elements.zoomIn.addEventListener('click', onZoomIn);
    elements.zoomOut.addEventListener('click', onZoomOut);
    elements.fitWidth.addEventListener('click', onFitWidth);
    
    // File selector change
    elements.fileSelector.addEventListener('change', async (e) => {
        const selectedFile = e.target.value;
        if (selectedFile && selectedFile !== app.currentFilename) {
            app.currentFilename = selectedFile;
            await loadPDF();
            await loadChunks();
        }
    });
    
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
                    <span class="info-label">File:</span>
                    <span class="info-value">${metadata.filename || 'unknown'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Type:</span>
                    <span class="info-value"><span class="chunk-type ${metadata.type || 'unknown'}">${metadata.type || 'unknown'}</span></span>
                </div>
                <div class="info-item">
                    <span class="info-label">Page Index:</span>
                    <span class="info-value">${metadata.page_idx !== undefined ? metadata.page_idx : 'N/A'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Source Collection:</span>
                    <span class="info-value">${chunk.source || 'unknown'}</span>
                </div>
            </div>
        </div>
    `;
    
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
}

// Close modal
function closeModal() {
    elements.modal.classList.remove('show');
}

// Style additions
const style = document.createElement('style');
style.textContent = `
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
    
    .pdf-page-placeholder {
        width: 100%;
        border: 1px solid #e0e0e0;
    }
`;

document.head.appendChild(style);

// Start the application
document.addEventListener('DOMContentLoaded', init);