#!/usr/bin/env python3
"""
Script to add filename metadata to existing chunks in ChromaDB.
This is a migration script for chunks that were created before filename support was added.
"""

import sys
import pathlib
import chromadb
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils import get_database

def update_chunks_with_filename(collection_name: str, filename: str = "manual") -> int:
    """
    Update all chunks in a collection to include filename metadata.
    
    Args:
        collection_name: Name of the collection ('textdb' or 'imgdb')
        filename: The filename to assign to all chunks
        
    Returns:
        Number of chunks updated
    """
    try:
        # Get collection
        storage = chromadb.PersistentClient("database/storage")
        collection = storage.get_collection(name=collection_name)
        
        # Get all chunks
        result = collection.get(include=['metadatas', 'documents'])
        
        if not result['ids']:
            print(f"No chunks found in {collection_name}")
            return 0
        
        updated_count = 0
        batch_size = 100  # Process in batches to avoid memory issues
        
        for i in range(0, len(result['ids']), batch_size):
            batch_ids = result['ids'][i:i + batch_size]
            batch_metadatas = result['metadatas'][i:i + batch_size]
            batch_documents = result['documents'][i:i + batch_size]
            
            # Check which chunks need filename updates
            ids_to_update = []
            metadatas_to_update = []
            documents_to_update = []
            
            for j, metadata in enumerate(batch_metadatas):
                if metadata is None:
                    metadata = {}
                
                # Only update if filename is missing or empty
                if not metadata.get('filename'):
                    metadata['filename'] = filename
                    ids_to_update.append(batch_ids[j])
                    metadatas_to_update.append(metadata)
                    documents_to_update.append(batch_documents[j])
                    updated_count += 1
            
            # Update chunks that need filename
            if ids_to_update:
                collection.update(
                    ids=ids_to_update,
                    metadatas=metadatas_to_update,
                    documents=documents_to_update
                )
                print(f"Updated batch: {len(ids_to_update)} chunks in {collection_name}")
        
        return updated_count
        
    except Exception as e:
        print(f"Error updating {collection_name}: {e}")
        return 0

def main():
    """Main function to update all collections."""
    print("Starting migration: Adding filename to existing chunks...")
    print("=" * 50)
    
    # Default filename for existing chunks
    default_filename = "manual"
    
    # Allow custom filename via command line
    if len(sys.argv) > 1:
        default_filename = sys.argv[1]
        print(f"Using custom filename: {default_filename}")
    else:
        print(f"Using default filename: {default_filename}")
    
    print()
    
    total_updated = 0
    collections = ['textdb', 'imgdb']
    
    for collection_name in collections:
        print(f"Processing collection: {collection_name}")
        try:
            updated = update_chunks_with_filename(collection_name, default_filename)
            total_updated += updated
            print(f"✓ Updated {updated} chunks in {collection_name}")
        except Exception as e:
            print(f"✗ Failed to update {collection_name}: {e}")
        print()
    
    print("=" * 50)
    print(f"Migration complete! Total chunks updated: {total_updated}")
    
    if total_updated > 0:
        print("\n📝 Summary:")
        print(f"- Added filename '{default_filename}' to {total_updated} chunks")
        print("- Existing chunks with filenames were left unchanged")
        print("- You can now use the multi-file chunk viewer!")
    else:
        print("\n✨ All chunks already have filename metadata!")

def verify_migration():
    """Verify the migration by checking chunk counts with/without filenames."""
    print("\n🔍 Verification:")
    print("-" * 30)
    
    try:
        storage = chromadb.PersistentClient("database/storage")
        
        for collection_name in ['textdb', 'imgdb']:
            try:
                collection = storage.get_collection(name=collection_name)
                result = collection.get(include=['metadatas'])
                
                total_chunks = len(result['ids'])
                chunks_with_filename = sum(1 for metadata in result['metadatas'] 
                                         if metadata and metadata.get('filename'))
                chunks_without_filename = total_chunks - chunks_with_filename
                
                print(f"{collection_name}:")
                print(f"  Total chunks: {total_chunks}")
                print(f"  With filename: {chunks_with_filename}")
                print(f"  Without filename: {chunks_without_filename}")
                print()
                
            except Exception as e:
                print(f"Error checking {collection_name}: {e}")
                
    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    # Run migration
    main()
    
    # Verify results
    verify_migration()