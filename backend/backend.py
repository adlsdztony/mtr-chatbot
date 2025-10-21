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
    """Create context with citation markers for the LLM."""
    context_parts = []
    
    # Add text chunks - use simple [1], [2] format
    for chunk in text_chunks:
        citation_num = chunk.get("citation_num", "?")
        content = chunk.get("content", "")
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "unknown")
        page = meta.get("page_idx", "?")
        
        context_parts.append(
            f"[{citation_num}]\n{content[:500]}...\n(from {filename}, page {page})"
        )
    
    # Add image/table information
    for chunk in image_chunks:
        citation_num = chunk.get("citation_num", "?")
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "unknown")
        page = meta.get("page_idx", "?")
        img_type = meta.get("type", "image")
        
        context_parts.append(
            f"[{citation_num}]\n{img_type.capitalize()} content\n(from {filename}, page {page})"
        )
    
    return "\n\n".join(context_parts)


def build_prompt_with_citations(question: str, text_chunks: List[Dict], image_chunks: List[Dict]) -> Tuple[str, str]:
    """Build system prompt and context with citations for the LLM."""
    citation_context = create_citation_context(text_chunks, image_chunks)
    
    complete_prompt = f"""Answer the following question using the reference sources below.

REFERENCE SOURCES:
{citation_context}

QUESTION: {question}

CITATION RULES:
- When you use information from a source, add its number in brackets at the end of the sentence
- Use ONLY the format [1] or [2] or [3] - nothing else!
- Do NOT write "Reference 1" or "Source 1" or "from [1]"
- Just add the bracket number at the end: [1]

EXAMPLES OF CORRECT CITATIONS:
✓ "The blue cable provides read-only access [1]."
✓ "It is used for downloads [2]."
✓ "Synchronization is required before use [3]."

EXAMPLES OF WRONG CITATIONS:
✗ "Reference 1 states that..."
✗ "According to Source [1]..."
✗ "From [1] (page 16)..."
✗ "...as described in [N]"

Now write your answer with correct [number] citations:"""
    
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