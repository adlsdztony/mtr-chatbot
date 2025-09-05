#!/usr/bin/env python3
"""
Launcher script for the Document Chunk Viewer
Run this script to start the Streamlit application
"""

import subprocess
import sys
import pathlib

def main():
    # Get the path to the chunk_viewer.py file
    script_dir = pathlib.Path(__file__).parent
    chunk_viewer_path = script_dir / "frontend" / "chunk_viewer.py"
    
    if not chunk_viewer_path.exists():
        print(f"Error: chunk_viewer.py not found at {chunk_viewer_path}")
        return 1
    
    # Run streamlit
    try:
        print("Starting Document Chunk Viewer...")
        print(f"Opening: {chunk_viewer_path}")
        print("Press Ctrl+C to stop the server")
        
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(chunk_viewer_path),
            "--server.port", "8502",  # Use a different port to avoid conflicts
            "--server.headless", "false"
        ])
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    except Exception as e:
        print(f"Error running streamlit: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())