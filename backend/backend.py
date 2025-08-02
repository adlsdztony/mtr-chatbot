import sys, pathlib

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_model import get_base_model
from utils.settings import VISION_MODEL, CHAT_MODEL
from utils.get_database import get_database
from loguru import logger


def get_knowledge(question: str):
    logger.info(f"Getting knowledge for question: {question}")

    textdb, imagedb = get_database("textdb"), get_database("imgdb")

    text_results = textdb.query(query_texts=question, n_results=3)
    image_results = imagedb.query(query_texts=question, n_results=2)

    if text_results["documents"] is None or not text_results["documents"]:
        logger.warning("No relevant text content found.")
        raise ValueError("No relevant text content found.")

    if image_results["metadatas"] is None or not image_results["metadatas"]:
        logger.warning("No relevant image content found.")
        raise ValueError("No relevant image content found.")

    return text_results["documents"][0], image_results["metadatas"][0] # type: ignore


def form_context_info(question: str):
    texts, images = get_knowledge(question)

    logger.debug("logging extracted texts ......")
    for chunk in texts:
        logger.debug(f"Text chunk:\n\t{chunk}...")

    for img in images:
        logger.debug(f"Image metadata: {img.get('path', '')}")

    return "\n".join(texts), images  # type: ignore
