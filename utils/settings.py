import os

PORT = 11434
CHAT_API_URL = os.getenv("OLLAMA_BASE_URL", f"http://localhost:{PORT}")

CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "deepseek-r1:8b")  
# qwen3:32b

VISION_MODEL = "qwen2.5vl:72b"
# gemma3:27b
# llava
# qwen2.5vl,  BUT IT'S GONE???
EMBEDDING_MODEL = "bge-m3:latest"