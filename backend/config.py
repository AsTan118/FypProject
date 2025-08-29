# config.py
from pathlib import Path

# Security Configuration
SECRET_KEY = "your-secret-key-change-this-in-production"  # Change this!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Database Configuration
DB_PATH = "../data/pdf_storage.db"
CHROMA_PATH = "../data/chroma_db"
PDF_FILES_PATH = "../data/pdf_files"

# Create directories if they don't exist
Path("../data").mkdir(exist_ok=True)
Path(PDF_FILES_PATH).mkdir(exist_ok=True)
Path(CHROMA_PATH).mkdir(exist_ok=True)

# Ollama Models Configuration
EMBEDDING_MODEL = "mxbai-embed-large"
LLM_MODEL = "llama3.2"

# LLM Configuration
LLM_CONFIG = {
    "temperature": 0.2,
    "top_p": 0.9,
    "num_ctx": 4096,
    "num_predict": 512,
}

# PDF Processing Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 1000
OVERLAP_SIZE = 200
MIN_CHUNK_LENGTH = 20

# API Configuration
CORS_ORIGINS = ["http://localhost:3000"]

# Prompt Template
PROMPT_TEMPLATE = """
You are an expert in answering questions about university information.

Here are some relevant excerpts from uploaded documents:
{context}

Question: {question}

Please provide a clear, helpful, and concise answer.
- Focus on summarizing what the documents say
- If the exact answer is not found, provide the closest related information
- Do not invent facts outside the documents
"""