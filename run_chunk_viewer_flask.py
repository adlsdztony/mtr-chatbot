#!/usr/bin/env python3
"""
Launch script for the Flask-based Document Chunk Viewer
"""

import subprocess
import sys
import pathlib
import webbrowser
import time
from threading import Timer

def open_browser():
    """Open browser after a short delay"""
    webbrowser.open('http://localhost:5001')

def main():
    # Get the path to the Flask app
    script_dir = pathlib.Path(__file__).parent
    app_path = script_dir / "frontend" / "chunk_viewer_app.py"
    
    if not app_path.exists():
        print(f"Error: Flask app not found at {app_path}")
        return 1
    
    print("🚀 Starting Document Chunk Viewer...")
    print(f"📁 App location: {app_path}")
    print("🌐 Server will start at: http://localhost:5001")
    print("⏰ Browser will open automatically in 3 seconds")
    print("🛑 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    # Open browser after 3 seconds
    Timer(3.0, open_browser).start()
    
    try:
        # Run the Flask app
        subprocess.run([
            sys.executable, str(app_path)
        ], cwd=str(script_dir))
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        return 0
    except Exception as e:
        print(f"❌ Error running Flask app: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())