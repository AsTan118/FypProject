# config.py - Improved configuration for better accuracy
import os

# CORS configuration
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "*"  # Allow all origins in development
]

# Paths
CHROMA_PATH = "chroma_db"
PDF_UPLOAD_PATH = "pdfs"

# Ensure directories exist
os.makedirs(CHROMA_PATH, exist_ok=True)
os.makedirs(PDF_UPLOAD_PATH, exist_ok=True)

# Ollama configuration - Using your installed models
EMBEDDING_MODEL = "mxbai-embed-large"  # Your embedding model
LLM_MODEL = "llama3.2"  # Your LLM model

# Improved LLM configuration for better answers
LLM_CONFIG = {
    "temperature": 0.3,  # Lower temperature for more focused answers
    "num_predict": 2000,  # Increased token limit for comprehensive answers
    "top_k": 40,  # Top-k sampling for better quality
    "top_p": 0.9,  # Nucleus sampling
    "repeat_penalty": 1.1,  # Avoid repetition
}

# Improved chunking configuration
CHUNK_SIZE = 800  # Smaller chunks for better precision
CHUNK_OVERLAP = 200  # Good overlap to maintain context
MIN_CHUNK_LENGTH = 100  # Minimum chunk size to avoid tiny fragments

# Retrieval configuration
RETRIEVAL_K = 8  # Retrieve more chunks for better context
SIMILARITY_THRESHOLD = 0.5  # Minimum similarity score for relevance

# Improved prompt template for better answers
PROMPT_TEMPLATE = """You are a helpful assistant analyzing PDF documents. Use the following context to answer the question accurately and comprehensively.

Context from PDFs:
{context}

Instructions:
1. Answer based ONLY on the information provided in the context above
2. If the context contains relevant information, provide a detailed and complete answer
3. Include specific details, examples, or data from the context when available
4. If multiple perspectives or pieces of information are present, synthesize them coherently
5. If the context doesn't contain enough information to fully answer the question, clearly state what information is available and what is missing
6. Do not make up information that is not in the context
7. Use clear formatting with paragraphs or bullet points when appropriate

Question: {question}

Answer:"""

# Alternative prompt for more technical documents
TECHNICAL_PROMPT_TEMPLATE = """You are a technical assistant analyzing PDF documents. Provide accurate, detailed answers based on the provided context.

Retrieved Context:
{context}

Technical Guidelines:
- Focus on accuracy and precision
- Include technical details, formulas, or specifications when present
- Maintain technical terminology from the source
- Provide step-by-step explanations when applicable
- Cite specific sections or page numbers if mentioned in context

Question: {question}

Technical Answer:"""

# JWT Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Database
DB_PATH = "rag_system.db"

# Vector store configuration
VECTOR_STORE_CONFIG = {
    "collection_name": "pdf_documents",
    "collection_metadata": {"hnsw:space": "cosine"},  # Use cosine similarity
    "persist_directory": CHROMA_PATH,
}

# Query configuration
QUERY_CONFIG = {
    "max_context_length": 4000,  # Maximum context to send to LLM
    "rerank_results": True,  # Whether to rerank results
    "use_mmr": True,  # Use Maximum Marginal Relevance for diversity
    "mmr_lambda": 0.5,  # Balance between relevance and diversity
}