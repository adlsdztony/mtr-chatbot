import os

class Config:
    # Environment detection
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    
    # Server configuration
    if ENVIRONMENT == 'production':
        SERVER_HOST = os.getenv('SERVER_HOST', '10.21.36.11')
        PDF_SERVER_PORT = os.getenv('PDF_SERVER_PORT', '8502')  
        STREAMLIT_PORT = os.getenv('STREAMLIT_PORT', '8501')
    else:
        # Development (localhost)
        SERVER_HOST = 'localhost'
        PDF_SERVER_PORT = os.getenv('PDF_SERVER_PORT', '8502')  # Can override
        STREAMLIT_PORT = '8501'
    
    # Build URLs
    PDF_SERVER_URL = f"http://{SERVER_HOST}:{PDF_SERVER_PORT}/pdfs"
    STREAMLIT_URL = f"http://{SERVER_HOST}:{STREAMLIT_PORT}"
    
    @classmethod
    def info(cls):
        """Print configuration for debugging"""
        return {
            'environment': cls.ENVIRONMENT,
            'server_host': cls.SERVER_HOST,
            'pdf_server_url': cls.PDF_SERVER_URL,
            'streamlit_url': cls.STREAMLIT_URL
        }