import sys, pathlib
import chromadb
from typing import Optional, List, Dict, Tuple

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
        for collection_name in ["textdb", "imgdb"]:
            try:
                collection = storage.get_collection(name=collection_name)
                result = collection.get(include=["metadatas"])

                for metadata in result["metadatas"]:
                    if metadata and "filename" in metadata:
                        available_files.add(metadata["filename"])
            except Exception as e:
                logger.warning(f"Error checking {collection_name}: {e}")

        # Add "all" option at the beginning
        files_list = ["all"] + sorted(list(available_files))
        return files_list
    except Exception as e:
        logger.error(f"Error getting available files: {e}")
        return ["all", "manual"]  # Fallback to all and manual


def get_knowledge(question: str, filename: Optional[str] = None):
    """Get knowledge with detailed chunk information for citations"""
    logger.info(f"Getting knowledge for question: {question}, filename: {filename}")

    textdb, imagedb = get_database("textdb"), get_database("imgdb")

    if filename and filename != "all":
        # Use metadata filters to query only chunks from the given filename

        text_results = textdb.query(
            query_texts=question, n_results=3, where={"filename": filename}
        )

        image_results = imagedb.query(
            query_texts=question, n_results=2, where={"filename": filename}
        )

    else:
        # Original behavior - query all (filename is None or "all")

        text_results = textdb.query(query_texts=question, n_results=3)

        image_results = imagedb.query(query_texts=question, n_results=2)

    if not text_results.get("documents") or not text_results["documents"][0]:
        logger.warning("No relevant text content found.")

        return [], []

    if not image_results.get("metadatas") or not image_results["metadatas"][0]:
        logger.warning("No relevant image content found.")

        image_results = {"metadatas": [[]], "ids": [[]]}

    # Return documents with their metadata for citation
    text_chunks_with_meta = []
    for i, doc in enumerate(text_results["documents"][0]):
        meta = (
            text_results["metadatas"][0][i]
            if i < len(text_results["metadatas"][0])
            else {}
        )
        text_chunks_with_meta.append(
            {
                "content": doc,
                "metadata": meta,
                "chunk_id": text_results["ids"][0][i]
                if i < len(text_results["ids"][0])
                else f"unknown_{i}",
                "citation_num": i + 1, 
            }
        )

    image_chunks_with_meta = []
    if image_results["metadatas"] and image_results["metadatas"][0]:
        for i, meta in enumerate(image_results["metadatas"][0]):
            image_chunks_with_meta.append(
                {
                    "metadata": meta,
                    "chunk_id": image_results["ids"][0][i]
                    if i < len(image_results["ids"][0])
                    else f"img_unknown_{i}",
                    "citation_num": len(text_chunks_with_meta) + i + 1,
                }
            )

    return text_chunks_with_meta, image_chunks_with_meta


def form_context_info(question: str, filename: Optional[str] = None):
    """Form context info with detailed chunk metadata for citations"""
    text_chunks, image_chunks = get_knowledge(question, filename)

    logger.debug("logging extracted texts ......")
    for chunk in text_chunks:
        logger.debug(
            f"Text chunk from {chunk.get('metadata', {}).get('filename', 'unknown')}:\n\t{chunk.get('content', '')[:100]}..."
        )

    for img in image_chunks:
        logger.debug(f"Image metadata: {img.get('metadata', {}).get('path', '')}")

    # Extract just the text content for the model
    texts = [chunk["content"] for chunk in text_chunks]
    # Extract legacy format for images
    images = [chunk["metadata"] for chunk in image_chunks if chunk.get("metadata")]

    return (
        "\n".join(texts),
        images,
        text_chunks,
        image_chunks,
    )  # Return both legacy and new format

def create_citation_context(text_chunks: List[Dict], image_chunks: List[Dict]) -> str:
    """
    Create context with citation markers for the LLM.
    Each chunk is tagged with [Source N] to help LLM know which source to cite.
    
    Returns:
        Context string with embedded citation markers
    """
    context_parts = []
    
    # Add text chunks with citation markers
    for chunk in text_chunks:
        citation_num = chunk.get("citation_num", "?")
        content = chunk.get("content", "")
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "unknown")
        page = meta.get("page_idx", "?")
        
        # Format: [Source N: filename, page X] content
        context_parts.append(
            f"[{citation_num}] (from {filename}, page {page}):\n{content}"
        )
    
    # Add image/table information
    for chunk in image_chunks:
        citation_num = chunk.get("citation_num", "?")
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "unknown")
        page = meta.get("page_idx", "?")
        img_type = meta.get("type", "image")
        
        context_parts.append(
            f"[Source {citation_num}: {filename}, page {page}]\n{img_type.capitalize()} available for reference."
        )
    
    return "\n\n---\n\n".join(context_parts)


def build_prompt_with_citations(question: str, text_chunks: List[Dict], image_chunks: List[Dict]) -> Tuple[str, str]:
    """
    Build system prompt and context with citations for the LLM.
    Generic version that works with any document type.
    
    Returns:
        Tuple of (complete_prompt, citation_context)
    """
    citation_context = create_citation_context(text_chunks, image_chunks)
    
    # Create a prompt that works with extended thinking models
    complete_prompt = f"""Answer the following question based on the provided reference sources.

Reference sources available:
{citation_context}

Question: {question}

CRITICAL INSTRUCTION FOR YOUR ANSWER:
When you write your answer, you MUST add citation numbers [1], [2], [3] at the END of each sentence that uses information from the sources above.

Example answer format:
"This is a fact from the document [1]. Here is another relevant detail [2]."

You can think through the problem, but when you provide your final answer, EVERY relevant sentence must end with a citation like [1], [2], etc.

Now provide your answer with proper citations:"""
    
    return complete_prompt, citation_context
    

def extract_citations_from_response(response_text: str, text_chunks: List[Dict], image_chunks: List[Dict]) -> List[Dict]:
    """
    Extract which citations were actually used in the response.
    
    Returns:
        List of citation dictionaries that were referenced in the response
    """
    import re
    
    # Find all citation numbers like [1], [2], etc.
    citation_pattern = r'\[(\d+)\]'
    cited_numbers = set(int(match) for match in re.findall(citation_pattern, response_text))
    
    # Build full citations list
    all_citations = []
    
    for chunk in text_chunks:
        citation_num = chunk.get("citation_num", 0)
        if citation_num in cited_numbers:
            meta = chunk.get("metadata", {})
            all_citations.append({
                "num": citation_num,
                "type": "text",
                "filename": meta.get("filename", "unknown"),
                "page_idx": meta.get("page_idx", 0),
                "chunk_id": chunk.get("chunk_id", ""),
                "preview": chunk.get("content", "")[:200] 
            })
    
    for chunk in image_chunks:
        citation_num = chunk.get("citation_num", 0)
        if citation_num in cited_numbers:
            meta = chunk.get("metadata", {})
            all_citations.append({
                "num": citation_num,
                "type": meta.get("type", "image"),
                "filename": meta.get("filename", "unknown"),
                "page_idx": meta.get("page_idx", 0),
                "chunk_id": chunk.get("chunk_id", ""),
                "preview": f"{meta.get('type', 'image')} on page {meta.get('page_idx', '?')}" 
            })
    
    # Sort by citation number
    all_citations.sort(key=lambda x: x["num"])
    
    return all_citations