# query/routes.py
from fastapi import APIRouter, Depends
from typing import Dict
import time
from models import QueryRequest
from auth.utils import verify_token

router = APIRouter(prefix="/api", tags=["query"])

# These will be set by main.py
vector_store = None
chain = None

def set_dependencies(store, llm_chain):
    """Set dependencies from main.py"""
    global vector_store, chain
    vector_store = store
    chain = llm_chain

@router.post("/query")
async def query_documents(
    request: QueryRequest,
    current_user: Dict = Depends(verify_token)
):
    """Query documents (protected)"""
    print(f"Query from {current_user['username']}: {request.question}")
    
    try:
        start_time = time.time()
        
        # Filter by user's documents
        retriever = vector_store.as_retriever(
            search_kwargs={
                "k": 10,
                "filter": {"user_id": current_user['user_id']}
            }
        )
        docs = retriever.invoke(request.question)
        
        if not docs:
            return {
                "answer": "No relevant documents found. Please upload some PDFs first.",
                "sources": [],
                "response_time": 0
            }
        
        context = "\n\n".join([
            f"From {doc.metadata.get('filename', 'Unknown')} page {doc.metadata.get('page', '?')}:\n{doc.page_content}"
            for doc in docs
        ])
        
        prompt_input = {
            "context": context,
            "question": request.question
        }
        result = chain.invoke(prompt_input)
        
        response_time = time.time() - start_time
        
        sources = [
            {
                "filename": doc.metadata.get('filename', 'Unknown'),
                "page": doc.metadata.get('page', 0),
                "snippet": doc.page_content[:250] + "..."
            }
            for doc in docs[:5]
        ]
        
        return {
            "answer": result,
            "sources": sources,
            "response_time": response_time
        }
    
    except Exception as e:
        print(f"Error in query: {e}")
        return {
            "answer": f"Error: {str(e)}",
            "sources": [],
            "response_time": 0
        }