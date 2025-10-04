import sys, pathlib
import chromadb
from typing import Optional

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_model import get_base_model
from utils.settings import VISION_MODEL, CHAT_MODEL
from utils.get_database import get_database
from loguru import logger


def get_available_files():
    """Get list of available files from database"""
    try:
        storage = chromadb.PersistentClient("database/storage")
        available_files = set()
        
        # Check both textdb and imgdb for filenames
        for collection_name in ['textdb', 'imgdb']:
            try:
                collection = storage.get_collection(name=collection_name)
                result = collection.get(include=['metadatas'])
                
                for metadata in result['metadatas']:
                    if metadata and 'filename' in metadata:
                        available_files.add(metadata['filename'])
            except Exception as e:
                logger.warning(f"Error checking {collection_name}: {e}")
        
        # Add "all" option at the beginning
        files_list = ['all'] + sorted(list(available_files))
        return files_list
    except Exception as e:
        logger.error(f"Error getting available files: {e}")
        return ['all', 'manual']  # Fallback to all and manual

def get_knowledge(question: str, filename: Optional[str] = None):
    """Get knowledge with detailed chunk information for citations"""
    logger.info(f"Getting knowledge for question: {question}, filename: {filename}")

    textdb, imagedb = get_database("textdb"), get_database("imgdb")

    # If filename is specified and not "all", we need to filter results
    if filename and filename != "all":
        # Get all chunks and filter by filename
        text_all = textdb.get(include=['documents', 'metadatas'])
        image_all = imagedb.get(include=['documents', 'metadatas'])
        
        # Filter by filename
        text_filtered_docs = []
        text_filtered_metas = []
        for i, meta in enumerate(text_all['metadatas']):
            if meta and meta.get('filename') == filename:
                text_filtered_docs.append(text_all['documents'][i])
                text_filtered_metas.append(meta)
        
        image_filtered_metas = []
        for meta in image_all['metadatas']:
            if meta and meta.get('filename') == filename:
                image_filtered_metas.append(meta)
        
        # Create temporary collection for querying
        import tempfile
        temp_storage = chromadb.Client()
        
        if text_filtered_docs:
            temp_text_collection = temp_storage.create_collection("temp_text")
            temp_text_collection.add(
                documents=text_filtered_docs,
                metadatas=text_filtered_metas,
                ids=[f"temp_text_{i}" for i in range(len(text_filtered_docs))]
            )
            text_results = temp_text_collection.query(query_texts=question, n_results=3)
        else:
            text_results = {"documents": [], "metadatas": [], "ids": []}
        
        # For images, we'll just return the filtered metadata
        image_results = {"metadatas": [image_filtered_metas[:2]], "ids": [f"img_{i}" for i in range(len(image_filtered_metas[:2]))]}
    else:
        # Original behavior - query all (filename is None or "all")
        text_results = textdb.query(query_texts=question, n_results=3)
        image_results = imagedb.query(query_texts=question, n_results=2)

    if text_results["documents"] is None or not text_results["documents"]:
        logger.warning("No relevant text content found.")
        return [], []

    if image_results["metadatas"] is None or not image_results["metadatas"]:
        logger.warning("No relevant image content found.")
        image_results = {"metadatas": [[]], "ids": []}

    # Return documents with their metadata for citation
    text_chunks_with_meta = []
    for i, doc in enumerate(text_results["documents"][0]):
        meta = text_results["metadatas"][0][i] if i < len(text_results["metadatas"][0]) else {}
        text_chunks_with_meta.append({
            "content": doc,
            "metadata": meta,
            "chunk_id": text_results["ids"][0][i] if i < len(text_results["ids"][0]) else f"unknown_{i}"
        })
    
    image_chunks_with_meta = []
    if image_results["metadatas"] and image_results["metadatas"][0]:
        for i, meta in enumerate(image_results["metadatas"][0]):
            image_chunks_with_meta.append({
                "metadata": meta,
                "chunk_id": image_results["ids"][0][i] if i < len(image_results["ids"][0]) else f"img_unknown_{i}"
            })

    return text_chunks_with_meta, image_chunks_with_meta


def form_context_info(question: str, filename: Optional[str] = None):
    """Form context info with detailed chunk metadata for citations"""
    text_chunks, image_chunks = get_knowledge(question, filename)

    logger.debug("logging extracted texts ......")
    for chunk in text_chunks:
        logger.debug(f"Text chunk from {chunk.get('metadata', {}).get('filename', 'unknown')}:\n\t{chunk.get('content', '')[:100]}...")

    for img in image_chunks:
        logger.debug(f"Image metadata: {img.get('metadata', {}).get('path', '')}")

    # Extract just the text content for the model
    texts = [chunk["content"] for chunk in text_chunks]
    # Extract legacy format for images
    images = [chunk["metadata"] for chunk in image_chunks if chunk.get("metadata")]
    
    return "\n".join(texts), images, text_chunks, image_chunks  # Return both legacy and new format
