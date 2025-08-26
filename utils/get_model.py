from langchain_ollama.chat_models import ChatOllama
from langchain_core.runnables import Runnable
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .settings import *


def get_base_model(use_model: str = CHAT_MODEL) -> ChatOllama:
    llm = ChatOllama(model=use_model, base_url=CHAT_API_URL)
    return llm


def get_prompted_model(use_model: str = CHAT_MODEL) -> Runnable:
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

    llm = prompt | ChatOllama(model=use_model, base_url=CHAT_API_URL) | StrOutputParser()
    return llm
