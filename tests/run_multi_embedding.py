import sys, pathlib
import os
from glob import glob
import chromadb

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from database.scripts.strategy.markdown import MarkdownEmbedding
from utils import get_database

def check_if_document_processed(filename: str) -> bool:
    """
    Check if a document has already been processed by looking for chunks with the filename.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if the document has already been processed, False otherwise
    """
    try:
        # Initialize ChromaDB client
        storage = chromadb.PersistentClient("database/storage")
        
        # Check both textdb and imgdb collections
        for collection_name in ['textdb', 'imgdb']:
            try:
                collection = storage.get_collection(name=collection_name)
                result = collection.get(include=['metadatas'])
                
                # Look for chunks with this filename
                for metadata in result['metadatas']:
                    if metadata and metadata.get('filename') == filename:
                        return True
                        
            except Exception:
                # Collection might not exist yet, continue checking
                continue
                
        return False
        
    except Exception as e:
        print(f"  [WARNING] Error checking if {filename} is processed: {e}")
        return False

def get_document_chunk_count(filename: str) -> dict:
    """
    Get the count of chunks for a specific document.
    
    Returns:
        Dictionary with counts from each collection
    """
    try:
        storage = chromadb.PersistentClient("database/storage")
        counts = {'textdb': 0, 'imgdb': 0, 'total': 0}
        
        for collection_name in ['textdb', 'imgdb']:
            try:
                collection = storage.get_collection(name=collection_name)
                result = collection.get(include=['metadatas'])
                
                count = sum(1 for metadata in result['metadatas']
                           if metadata and metadata.get('filename') == filename)
                counts[collection_name] = count
                counts['total'] += count
                
            except Exception:
                continue
                
        return counts
        
    except Exception:
        return {'textdb': 0, 'imgdb': 0, 'total': 0}

def process_multiple_documents(data_dir: str = ".data/result", force: bool = False):
    """
    Process multiple documents from the data directory.
    
    Args:
        data_dir: Directory containing document folders
        force: If True, reprocess documents even if they already exist in database
    
    Expected structure:
    .data/result/
    ├── document1/
    │   ├── document1_content_list.json
    │   └── document1.md
    ├── document2/
    │   ├── document2_content_list.json
    │   └── document2.md
    └── ...
    """
    
    data_path = pathlib.Path(data_dir)
    
    if not data_path.exists():
        print(f"Data directory {data_dir} does not exist!")
        return
    
    # Find all subdirectories (each represents a document)
    document_dirs = [d for d in data_path.iterdir() if d.is_dir()]
    
    if not document_dirs:
        print(f"No document directories found in {data_dir}")
        return
        
    print(f"Found {len(document_dirs)} document directories:")
    for doc_dir in document_dirs:
        print(f"  - {doc_dir.name}")
    
    print(f"\nForce mode: {'ON' if force else 'OFF'}")
    print("=" * 60)
    
    # Statistics
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Process each document
    for doc_dir in document_dirs:
        doc_name = doc_dir.name
        # if there is a auto dir inside, use it as the doc_dir
        auto_dir = doc_dir / "auto"
        if auto_dir.exists() and auto_dir.is_dir():
            doc_dir = auto_dir
        print(f"\n=== Processing document: {doc_name} ===")
        
        doc_processed = check_if_document_processed(doc_name)
        # Check if already processed (unless force mode is on)
        if not force and doc_processed:
            chunk_counts = get_document_chunk_count(doc_name)
            print(f"  [SKIP] Document already processed:")
            print(f"    - Text chunks: {chunk_counts['textdb']}")
            print(f"    - Image/Table chunks: {chunk_counts['imgdb']}")
            print(f"    - Total chunks: {chunk_counts['total']}")
            print(f"    Use --force to reprocess")
            skipped_count += 1
            continue

        if force and doc_processed:
            # delete existing chunks for this document
            print(f"  [FORCE] Reprocessing document, deleting existing chunks...")
            try:
                storage = chromadb.PersistentClient("database/storage")
                for collection_name in ['textdb', 'imgdb']:
                    try:
                        collection = storage.get_collection(name=collection_name)
                        result = collection.get(include=['ids', 'metadatas'])
                        ids_to_delete = [result['ids'][i] for i, metadata in enumerate(result['metadatas'])
                                         if metadata and metadata.get('filename') == doc_name]
                        if ids_to_delete:
                            collection.delete(ids=ids_to_delete)
                            print(f"    - Deleted {len(ids_to_delete)} chunks from {collection_name}")
                    except Exception:
                        continue
            except Exception as e:
                print(f"  [ERROR] Failed to delete existing chunks: {e}")
                error_count += 1
                continue
        
        # Look for JSON and markdown files
        json_files = list(doc_dir.glob("*_content_list.json"))
        md_files = list(doc_dir.glob("*.md"))
        
        if not json_files:
            print(f"  [SKIP] No *_content_list.json found in {doc_name}")
            skipped_count += 1
            continue
            
        if not md_files:
            print(f"  [SKIP] No .md files found in {doc_name}")
            skipped_count += 1
            continue
        
        # Use the first JSON file and first MD file found
        json_file = json_files[0]
        md_file = md_files[0]
        
        print(f"  JSON: {json_file.name}")
        print(f"  Markdown: {md_file.name}")
        
        try:
            # Initialize processor with filename
            processor = MarkdownEmbedding(
                json_path=str(json_file),
                markdown_path=str(md_file),
                filename=doc_name
            )
            
            # Execute processing
            processor.run()
            
            # Show final chunk counts
            chunk_counts = get_document_chunk_count(doc_name)
            print(f"  [OK] Successfully processed {doc_name}")
            print(f"    - Text chunks: {chunk_counts['textdb']}")
            print(f"    - Image/Table chunks: {chunk_counts['imgdb']}")
            print(f"    - Total chunks: {chunk_counts['total']}")
            processed_count += 1
            
        except Exception as e:
            print(f"  [ERROR] Failed to process {doc_name}: {e}")
            error_count += 1
            continue
    
    # Final statistics
    print("\n" + "=" * 60)
    print("📊 PROCESSING SUMMARY:")
    print(f"   ✅ Processed: {processed_count} documents")
    print(f"   ⏭️  Skipped: {skipped_count} documents")
    print(f"   ❌ Errors: {error_count} documents")
    print(f"   📁 Total found: {len(document_dirs)} documents")
    
    if skipped_count > 0 and not force:
        print(f"\n💡 TIP: Use --force to reprocess skipped documents")
    
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Process multiple documents for embedding")
    parser.add_argument("data_dir", nargs="?", default=".data/result", 
                       help="Directory containing document folders (default: .data/result)")
    parser.add_argument("--force", action="store_true", 
                       help="Force reprocessing of already processed documents")
    
    args = parser.parse_args()
    
    print("🚀 Multi-Document Embedding Processor")
    print(f"📂 Data directory: {args.data_dir}")
    print(f"🔄 Force mode: {'Enabled' if args.force else 'Disabled'}")
    print()
    
    process_multiple_documents(args.data_dir, args.force)