# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import configuration
from config import CORS_ORIGINS, CHROMA_PATH, EMBEDDING_MODEL, LLM_MODEL, LLM_CONFIG, PROMPT_TEMPLATE

# Import database initialization
from database import init_database

# Import routers
from auth.routes import router as auth_router
from pdf.routes import router as pdf_router, set_vector_store
from query.routes import router as query_router, set_dependencies

# LangChain imports
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate

# Initialize FastAPI app
app = FastAPI(title="Enhanced PDF RAG System with Auth")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_database()

# Initialize Ollama components
print("Initializing Ollama components...")
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
llm = OllamaLLM(model=LLM_MODEL, **LLM_CONFIG)

# Initialize vector store
vector_store = Chroma(
    collection_name="pdf_documents",
    persist_directory=CHROMA_PATH,
    embedding_function=embeddings
)

# Create chain for RAG
prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
chain = prompt | llm

# Set dependencies for routers
set_vector_store(vector_store)
set_dependencies(vector_store, chain)

# Include routers
app.include_router(auth_router)
app.include_router(pdf_router)
app.include_router(query_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "Enhanced PDF RAG System with Authentication",
        "version": "2.0",
        "models": {
            "llm": LLM_MODEL,
            "embeddings": EMBEDDING_MODEL
        },
        "endpoints": {
            "auth": "/api/auth",
            "pdfs": "/api/pdfs",
            "query": "/api/query"
        }
    }

if __name__ == "__main__":
    print("\n" + "="*70)
    print("PDF RAG SYSTEM WITH AUTHENTICATION")
    print("="*70)
    print("\n📋 SETUP INSTRUCTIONS:")
    print("1. Install requirements:")
    print("   pip install fastapi uvicorn pdfplumber")
    print("   pip install langchain-ollama langchain-chroma")
    print("   pip install pyjwt bcrypt python-multipart")
    print("\n2. Ensure Ollama is running with required models:")
    print(f"   - ollama pull {LLM_MODEL}")
    print(f"   - ollama pull {EMBEDDING_MODEL}")
    print("\n3. IMPORTANT: Change SECRET_KEY in config.py for production!")
    print("\n🌐 SERVER:")
    print("Starting at: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)