from langchain_ollama.chat_models import ChatOllama
from langchain_core.runnables import Runnable, RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List, Dict
from .settings import *

# Default parameter values for LLM configuration
DEFAULT_PARAMETERS = {
    "temperature": 0.7,    # Range: 0.0 - 2.0, controls randomness
    "top_p": 0.9,         # Range: 0.0 - 1.0, nucleus sampling parameter
    "top_k": 40           # Range: 1 - 100, top-k sampling parameter
}


class InMemoryChatMessageHistory(BaseChatMessageHistory, BaseModel):
    """
    In-memory implementation of chat message history.
    Stores messages for a conversation session.
    """
    messages: List[BaseMessage] = Field(default_factory=list)

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the store"""
        self.messages.append(message)

    def clear(self) -> None:
        """Clear all messages"""
        self.messages = []


# Global store for all session histories
_session_store = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """
    Retrieve or create chat history for a given session ID.
    
    Args:
        session_id: Unique identifier for the chat session
    
    Returns:
        Chat message history for the session
    """
    if session_id not in _session_store:
        _session_store[session_id] = InMemoryChatMessageHistory()
    return _session_store[session_id]


def add_referenced_context_to_history(
    session_id: str,
    text_chunks: List[Dict],
    image_chunks: List[Dict]
) -> None:
    """
    Add the RAG-retrieved context that AI referenced to the chat history.
    This allows the model to refer back to previously retrieved content in follow-up questions.
    
    Solution A: Save full referenced context without length limit.
    The context is saved as a system message to distinguish it from user/AI messages.
    
    Args:
        session_id: Session identifier for the chat history
        text_chunks: List of text chunks retrieved from RAG (with metadata)
        image_chunks: List of image chunks retrieved from RAG (with metadata)
    """
    history = get_session_history(session_id)
    
    # Build a formatted context string with all retrieved sources
    context_parts = []
    
    context_parts.append("=" * 50)
    context_parts.append("REFERENCED CONTEXT FROM RAG RETRIEVAL")
    context_parts.append("=" * 50)
    context_parts.append("")
    
    # Add text chunks
    if text_chunks:
        context_parts.append("📄 TEXT SOURCES:")
        context_parts.append("-" * 50)
        for chunk in text_chunks:
            citation_num = chunk.get("citation_num", "?")
            content = chunk.get("content", "")
            meta = chunk.get("metadata", {})
            filename = meta.get("filename", "unknown")
            page = meta.get("page_idx", "?")
            chunk_type = meta.get("type", "text")
            
            context_parts.append(f"\n[Source {citation_num}]")
            context_parts.append(f"File: {filename} | Page: {page} | Type: {chunk_type}")
            context_parts.append(f"Content:\n{content}")
            context_parts.append("-" * 50)
    
    # Add image/table chunks
    if image_chunks:
        context_parts.append("\n🖼️ IMAGE/TABLE SOURCES:")
        context_parts.append("-" * 50)
        for chunk in image_chunks:
            citation_num = chunk.get("citation_num", "?")
            meta = chunk.get("metadata", {})
            filename = meta.get("filename", "unknown")
            page = meta.get("page_idx", "?")
            chunk_type = meta.get("type", "image")
            path = meta.get("path", "")
            
            context_parts.append(f"\n[Source {citation_num}]")
            context_parts.append(f"File: {filename} | Page: {page} | Type: {chunk_type}")
            if path:
                context_parts.append(f"Path: {path}")
            context_parts.append("-" * 50)
    
    context_parts.append("")
    context_parts.append("=" * 50)
    context_parts.append("END OF REFERENCED CONTEXT")
    context_parts.append("=" * 50)
    
    # Combine all parts into a single context string
    full_context = "\n".join(context_parts)
    
    # Add as a system message to preserve it in history
    context_message = SystemMessage(content=full_context)
    history.add_message(context_message)



def get_base_model(
    use_model: str = CHAT_MODEL,
    temperature: float = DEFAULT_PARAMETERS["temperature"],
    top_p: float = DEFAULT_PARAMETERS["top_p"],
    top_k: int = DEFAULT_PARAMETERS["top_k"]
) -> ChatOllama:
    """
    Create a base ChatOllama model with configurable parameters.
    
    Args:
        use_model: Model name to use
        temperature: Controls randomness in output (0.0-2.0)
        top_p: Nucleus sampling parameter (0.0-1.0)
        top_k: Top-k sampling parameter (1-100)
    
    Returns:
        Configured ChatOllama instance
    """
    llm = ChatOllama(
        model=use_model, 
        base_url=CHAT_API_URL,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k
    )
    return llm


def get_prompted_model(
    use_model: str = CHAT_MODEL,
    temperature: float = DEFAULT_PARAMETERS["temperature"],
    top_p: float = DEFAULT_PARAMETERS["top_p"],
    top_k: int = DEFAULT_PARAMETERS["top_k"]
) -> Runnable:
    """
    Create a prompted model chain with configurable parameters and conversation history support.
    
    Args:
        use_model: Model name to use
        temperature: Controls randomness in output (0.0-2.0)
        top_p: Nucleus sampling parameter (0.0-1.0)
        top_k: Top-k sampling parameter (1-100)
    
    Returns:
        Configured Runnable model chain with message history support
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful RAG assistant. Follow these rules:

1. Evaluate the style of your answer based on the type of question. For example, if the question is about listing steps, then you should be faithful to the original text and avoid summarizing. For example, if the question is about summarizing a text, then you should summarize the text and avoid listing steps.
2. If the context is not sufficient to answer the question or is not relevant to the question, please say "I don't know" or "I cannot answer this question based on the provided context." DO NOT make up answers. But if you can answer the question based on the provided context, please answer it.
3. Use the provided context only to answer the question. Do not make up assumptions or guesses.
4. Use the conversation history to understand the context of follow-up questions and maintain continuity in the conversation.
5. Ensure clarity, conciseness, and factual accuracy. You must not guess or suggest any technical steps.

# Context Information
{context_info}"""),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}")
    ])

    
    llm = ChatOllama(
        model=use_model, 
        base_url=CHAT_API_URL,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        reasoning=True
    )
    
    chain = prompt | llm | StrOutputParser()
    
    # Wrap the chain with message history support
    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="question",
        history_messages_key="history",
    )
    
    return chain_with_history


def validate_parameters(
    temperature: float,
    top_p: float,
    top_k: int
) -> tuple[bool, str]:
    """
    Validate parameter ranges and constraints.
    
    Args:
        temperature: Temperature value to validate (0.0-2.0)
        top_p: Top-p value to validate (0.0-1.0)
        top_k: Top-k value to validate (1-100)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not (0.0 <= temperature <= 2.0):
        return False, "Temperature must be between 0.0 and 2.0"
    
    if not (0.0 <= top_p <= 1.0):
        return False, "Top-p must be between 0.0 and 1.0"
    
    if not (1 <= top_k <= 100):
        return False, "Top-k must be between 1 and 100"
    
    return True, ""


def get_prompted_model_with_params(
    use_model: str = CHAT_MODEL,
    temperature: float = DEFAULT_PARAMETERS["temperature"],
    top_p: float = DEFAULT_PARAMETERS["top_p"],
    top_k: int = DEFAULT_PARAMETERS["top_k"]
) -> Runnable:
    """
    Create a prompted model with validated parameters.
    
    Args:
        use_model: Model name to use
        temperature: Controls randomness in output (0.0-2.0)
        top_p: Nucleus sampling parameter (0.0-1.0)
        top_k: Top-k sampling parameter (1-100)
    
    Returns:
        Configured Runnable model chain
    
    Raises:
        ValueError: If parameters are out of valid ranges
    """
    # Validate parameters
    is_valid, error_msg = validate_parameters(temperature, top_p, top_k)
    if not is_valid:
        raise ValueError(f"Invalid parameter: {error_msg}")
    
    return get_prompted_model(use_model, temperature, top_p, top_k)
