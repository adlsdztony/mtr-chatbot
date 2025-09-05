"""
Script to check the status of chunks in the database
"""
import sys
import pathlib
import chromadb

# Get the base paths relative to this file
CURRENT_DIR = pathlib.Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent

# Add parent directory to path
sys.path.append(str(PROJECT_ROOT))

def check_database():
    """Check the contents of the ChromaDB collections"""
    
    # Initialize ChromaDB client - path relative to main project
    DB_PATH = PROJECT_ROOT / "database" / "storage"
    storage = chromadb.PersistentClient(str(DB_PATH))
    
    # Get all collections
    collections = storage.list_collections()
    
    if not collections:
        print("No collections found in the database.")
        print("Please run the embedding script first:")
        print("  uv run python tests/run_embedding.py")
        return
    
    print(f"Found {len(collections)} collection(s):\n")
    
    for collection in collections:
        print(f"Collection: {collection.name}")
        print("-" * 40)
        
        # Get collection data
        result = collection.get(
            include=['documents', 'metadatas']
        )
        
        num_items = len(result['ids'])
        print(f"  Total items: {num_items}")
        
        if num_items > 0:
            # Count by type
            type_counts = {}
            for metadata in result['metadatas']:
                if metadata:
                    item_type = metadata.get('type', 'unknown')
                    type_counts[item_type] = type_counts.get(item_type, 0) + 1
            
            print("  Items by type:")
            for item_type, count in type_counts.items():
                print(f"    - {item_type}: {count}")
            
            # Show sample items
            print("\n  Sample items (first 3):")
            for i in range(min(3, num_items)):
                print(f"\n    Item {i+1}:")
                print(f"      ID: {result['ids'][i]}")
                if result['metadatas'][i]:
                    print(f"      Metadata: {result['metadatas'][i]}")
                if result['documents'][i]:
                    doc_preview = result['documents'][i][:100]
                    print(f"      Document preview: {doc_preview}...")
        else:
            print("  No items in this collection.")
        
        print()

if __name__ == "__main__":
    check_database()