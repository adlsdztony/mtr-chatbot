#!/usr/bin/env python
"""
Launch script for the Chunk Viewer UI
"""
import sys
import pathlib
import webbrowser
from threading import Timer

sys.path.append(pathlib.Path(__file__).parent.as_posix())

def open_browser():
    """Open the browser after a short delay"""
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("=" * 60)
    print("CHUNK VIEWER - Document Chunk Debugging Tool")
    print("=" * 60)
    print()
    print("Starting Flask server...")
    print("The UI will open in your browser at: http://localhost:5000")
    print()
    print("To stop the server, press Ctrl+C")
    print("-" * 60)
    
    # Open browser after 1.5 seconds
    Timer(1.5, open_browser).start()
    
    # Import and run the Flask app
    from app import app
    app.run(debug=True, port=5000, use_reloader=False)