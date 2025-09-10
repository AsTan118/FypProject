# main.py - Enhanced version with better RAG configuration
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio

# Import improved configuration
from config import (
    CORS_ORIGINS, VECTOR_STORE_CONFIG, EMBEDDING_MODEL, 
    LLM_MODEL, LLM_CONFIG, PROMPT_TEMPLATE, CHUNK_SIZE, CHUNK_OVERLAP
)

# Import database initialization
from database import init_database

# LangChain imports
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate

# Initialize FastAPI app
app = FastAPI(title="Enhanced PDF RAG System with Improved Accuracy")

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

# Initialize enhanced Ollama components
print("Initializing enhanced Ollama components...")
vector_store = None
chain = None
llm = None
embeddings = None

try:
    # Initialize embeddings without show_progress parameter
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL
    )
    
    # Test embeddings
    test_embedding = embeddings.embed_query("test")
    print(f"✅ Embeddings working - dimension: {len(test_embedding)}")
    
    # Initialize LLM with optimized settings
    llm = OllamaLLM(
        model=LLM_MODEL,
        **LLM_CONFIG
    )
    
    # Test LLM
    test_response = llm.invoke("Say 'OK' if you're working")
    print(f"✅ LLM working - test response received")
    
    # Initialize vector store with enhanced configuration
    vector_store = Chroma(
        **VECTOR_STORE_CONFIG,
        embedding_function=embeddings
    )
    
    # Create enhanced chain for RAG
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | llm
    
    print("✅ Enhanced Ollama components initialized successfully")
    print(f"   - Embedding Model: {EMBEDDING_MODEL}")
    print(f"   - LLM Model: {LLM_MODEL}")
    print(f"   - Temperature: {LLM_CONFIG.get('temperature')}")
    print(f"   - Chunk Size: {CHUNK_SIZE}")
    print(f"   - Chunk Overlap: {CHUNK_OVERLAP}")
    
except Exception as e:
    print(f"❌ ERROR: Could not initialize Ollama components: {e}")
    print("\n⚠️  TROUBLESHOOTING:")
    print("1. Make sure Ollama is running: 'ollama serve'")
    print("2. Install required models:")
    print(f"   ollama pull {EMBEDDING_MODEL}")
    print(f"   ollama pull {LLM_MODEL}")
    print("3. Check if ports are available (default: 11434)")
    print("\nThe system will run in LIMITED MODE - uploads work but queries will fail")
    vector_store = None
    chain = None
    llm = None
    embeddings = None

# Import routers AFTER initializing components
from auth.routes import router as auth_router
from pdf.routes import router as pdf_router, set_vector_store, cleanup_stuck_pdfs
from query.routes import router as query_router, set_dependencies

# Import admin router
try:
    from admin.routes import router as admin_router
    has_admin = True
except ImportError as e:
    print(f"Warning: Could not import admin router: {e}")
    has_admin = False

# Set enhanced dependencies for routers
if vector_store:
    set_vector_store(vector_store)
    set_dependencies(vector_store, chain, llm, embeddings)

# Include routers
app.include_router(auth_router)
app.include_router(pdf_router)
app.include_router(query_router)

if has_admin:
    app.include_router(admin_router)
    print("✅ Admin router loaded successfully")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    print("Running startup tasks...")
    
    # Schedule cleanup of stuck PDFs
    asyncio.create_task(cleanup_stuck_pdfs())
    
    # Optimize vector store if it exists
    if vector_store:
        try:
            # Get collection to ensure it's initialized
            collection = vector_store._collection
            if collection:
                print(f"Vector store collection '{collection.name}' is ready")
                # You can add index optimization here if needed
        except Exception as e:
            print(f"Warning: Could not optimize vector store: {e}")
    
    print("Startup tasks completed")

# Root endpoint
@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "Enhanced PDF RAG System with Improved Accuracy",
        "version": "4.0",
        "configuration": {
            "llm": {
                "model": LLM_MODEL,
                "temperature": LLM_CONFIG.get("temperature"),
                "max_tokens": LLM_CONFIG.get("num_predict")
            },
            "embeddings": {
                "model": EMBEDDING_MODEL
            },
            "chunking": {
                "size": CHUNK_SIZE,
                "overlap": CHUNK_OVERLAP
            },
            "retrieval": {
                "k": 8,
                "use_mmr": True
            }
        },
        "endpoints": {
            "auth": "/api/auth",
            "pdfs": "/api/pdfs",
            "query": "/api/query",
            "advanced_query": "/api/query/advanced",
            "admin": "/api/admin" if has_admin else "not available"
        },
        "status_checks": {
            "database": "connected",
            "vector_store": "ready" if vector_store else "not available",
            "llm": "ready" if chain else "not available"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Detailed health check"""
    health_status = {
        "status": "healthy",
        "components": {
            "database": "connected",
            "vector_store": "ready" if vector_store else "not available",
            "llm": "ready" if llm else "not available",
            "embeddings": "ready" if embeddings else "not available"
        }
    }
    
    # Test vector store
    if vector_store:
        try:
            # Try a simple query to test
            test_results = vector_store.similarity_search("test", k=1)
            health_status["components"]["vector_store_test"] = "passed"
        except:
            health_status["components"]["vector_store_test"] = "failed"
    
    return health_status

# Tips endpoint for better usage
@app.get("/api/tips")
async def get_usage_tips():
    """Get tips for better query results"""
    return {
        "tips": [
            "Be specific in your questions - include key terms from the document",
            "Ask for specific information rather than general summaries",
            "If you don't get good results, try rephrasing your question",
            "Use the advanced query endpoint for complex questions",
            "Mention the document name if you're looking for information from a specific PDF",
            "Break complex questions into multiple simpler queries",
            "Use quotation marks for exact phrases you're looking for"
        ],
        "example_queries": [
            "What are the main findings in the research paper about climate change?",
            "List all the requirements mentioned in the project specification document",
            "What is the definition of 'machine learning' according to the PDF?",
            "Compare the advantages and disadvantages discussed in the document",
            "What are the steps for the installation process?"
        ]
    }

if __name__ == "__main__":
    print("\n" + "="*70)
    print("ENHANCED PDF RAG SYSTEM - VERSION 4.0")
    print("="*70)
    
    print("\n📋 OPTIMIZED CONFIGURATION:")
    print(f"  - LLM Model: {LLM_MODEL}")
    print(f"  - Embedding Model: {EMBEDDING_MODEL}")
    print(f"  - Temperature: {LLM_CONFIG.get('temperature')} (lower = more focused)")
    print(f"  - Chunk Size: {CHUNK_SIZE} chars")
    print(f"  - Chunk Overlap: {CHUNK_OVERLAP} chars")
    print(f"  - Retrieval K: 8 chunks")
    print(f"  - Using MMR: Yes (for diverse results)")
    
    print("\n🎯 TIPS FOR BETTER RESULTS:")
    print("  1. Ask specific questions with key terms")
    print("  2. Use the advanced query endpoint for complex questions")
    print("  3. Ensure PDFs are fully processed before querying")
    print("  4. Keep questions focused on single topics")
    
    print("\n📦 REQUIRED MODELS:")
    print(f"  ollama pull {LLM_MODEL}")
    print(f"  ollama pull {EMBEDDING_MODEL}")
    
    print("\n🌐 ENDPOINTS:")
    print("  Main: http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("  Tips: http://localhost:8000/api/tips")
    print("="*70 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
        log_level="info"
    )