import chromadb
import numpy as np
from .settings import *
from chromadb import Documents, Embeddings, EmbeddingFunction, Collection
from langchain_ollama import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

storage = chromadb.PersistentClient("database/storage")


class MultiModalEmbedding(EmbeddingFunction):
    def __init__(self):
        self.embedder = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=CHAT_API_URL,
        )

    def __call__(self, inputs: Documents) -> Embeddings:
        embeddings = self.embedder.embed_documents(inputs)
        return [np.asarray(embedding) for embedding in embeddings]


def get_database(name: str) -> Collection:
    """
    Get a ChromaDB collection by name, creating it if it doesn't exist.

    Args:
        name (str): The name of the collection to retrieve or create.

    Returns:
        Collection: The ChromaDB collection.
    """
    return storage.get_or_create_collection(name=name)

def get_text_splitter(chunk_size: int = 2000, chunk_overlap: int = 500):
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )