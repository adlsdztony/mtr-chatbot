from langchain_ollama.chat_models import ChatOllama
from langchain_core.runnables import Runnable
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .settings import *

# Default parameter values for LLM configuration
DEFAULT_PARAMETERS = {
    "temperature": 0.7,    # Range: 0.0 - 2.0, controls randomness
    "top_p": 0.9,         # Range: 0.0 - 1.0, nucleus sampling parameter
    "top_k": 40           # Range: 1 - 100, top-k sampling parameter
}


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
    prompt = PromptTemplate.from_template(
        """
# Context Information
{context_info}

-----

# Instructions

Read the context first. Then solve the user's question step by step. Also follow these rules:

1. Evaluate the style of your answer based on the type of question. For example, if the question is about listing steps, then you should be faithful to the original text and avoid summarizing. For example, if the question is about summarizing a text, then you should summarize the text and avoid listing steps.
2. If the context is not sufficient to answer the question or is not relevant to the question, please say "I don't know" or "I cannot answer this question based on the provided context." DO NOT make up answers. But if you can answer the question based on the provided context, please answer it.
3. Use the provided context only to answer the question. Do not make up assumptions or guesses.
4. Ensure clarity, conciseness, and factual accuracy. You must not guess or suggest any technical steps.

-----

# User Question
{question}
"""
    )

    """
    Create a prompted model chain with configurable parameters.
    
    Args:
        use_model: Model name to use
        temperature: Controls randomness in output (0.0-2.0)
        top_p: Nucleus sampling parameter (0.0-1.0)
        top_k: Top-k sampling parameter (1-100)
    
    Returns:
        Configured Runnable model chain
    """
    llm = prompt | ChatOllama(
        model=use_model, 
        base_url=CHAT_API_URL,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k
    ) | StrOutputParser()
    return llm


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
