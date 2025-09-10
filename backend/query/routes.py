# query/routes.py - Improved version with better retrieval and answer generation
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from auth.utils import get_current_user
from database import get_db_connection
import time
import json
from config import RETRIEVAL_K, SIMILARITY_THRESHOLD, QUERY_CONFIG

router = APIRouter(prefix="/api", tags=["Query"])

# Global variables for dependencies
vector_store = None
chain = None
llm = None
embeddings = None

def set_dependencies(vs, ch, llm_instance=None, emb=None):
    """Set vector store and chain instances"""
    global vector_store, chain, llm, embeddings
    vector_store = vs
    chain = ch
    llm = llm_instance
    embeddings = emb

class QueryRequest(BaseModel):
    question: str
    
class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    response_time: float
    confidence: Optional[float] = None

def rerank_results(query: str, results: list) -> list:
    """Rerank results based on relevance to query"""
    # Simple keyword-based reranking
    query_words = set(query.lower().split())
    
    reranked = []
    for doc, score in results:
        content_words = set(doc.page_content.lower().split())
        keyword_overlap = len(query_words.intersection(content_words)) / len(query_words)
        
        # Combine original score with keyword overlap
        combined_score = (score * 0.7) + (keyword_overlap * 0.3)
        reranked.append((doc, combined_score))
    
    # Sort by combined score
    reranked.sort(key=lambda x: x[1], reverse=False)  # Lower scores are better in Chroma
    return reranked

def prepare_context(results: list, max_length: int = 4000) -> str:
    """Prepare context from search results with deduplication and relevance ordering"""
    seen_content = set()
    context_parts = []
    current_length = 0
    
    for doc, score in results:
        # Check if we've seen similar content
        content_hash = hash(doc.page_content[:100])  # Use first 100 chars as fingerprint
        if content_hash in seen_content:
            continue
        seen_content.add(content_hash)
        
        # Add source information
        metadata = doc.metadata
        source_info = f"[Source: {metadata.get('filename', 'Unknown')}, Page {metadata.get('page', 'N/A')}]"
        
        # Add content with source
        content_with_source = f"{source_info}\n{doc.page_content}\n"
        
        # Check length
        if current_length + len(content_with_source) > max_length:
            break
        
        context_parts.append(content_with_source)
        current_length += len(content_with_source)
    
    return "\n---\n".join(context_parts)

@router.post("/query", response_model=QueryResponse)
async def query_pdfs(
    query_request: QueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Query the PDFs using improved RAG"""
    # Check if system is initialized
    if not vector_store:
        print("ERROR: Vector store not initialized")
        return QueryResponse(
            answer="The query system is not properly initialized. Please contact the administrator to ensure Ollama is running and the required models are installed.",
            sources=[],
            response_time=0,
            confidence=0.0
        )
    
    if not chain:
        print("ERROR: LLM chain not initialized")
        return QueryResponse(
            answer="The language model is not available. Please ensure Ollama is running with the required model.",
            sources=[],
            response_time=0,
            confidence=0.0
        )
    
    start_time = time.time()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get accessible PDF IDs based on user role
        if current_user['role'] == 'admin':
            cursor.execute('SELECT id FROM pdfs WHERE processing_status = "completed"')
        else:
            cursor.execute('''
                SELECT id FROM pdfs 
                WHERE processing_status = "completed" 
                AND (user_id = ? OR visibility = "public")
            ''', (current_user['id'],))
        
        accessible_pdf_ids = [row['id'] for row in cursor.fetchall()]
        
        if not accessible_pdf_ids:
            return QueryResponse(
                answer="No accessible PDFs found. Please upload PDFs or wait for processing to complete.",
                sources=[],
                response_time=time.time() - start_time,
                confidence=0.0
            )
        
        print(f"Searching in {len(accessible_pdf_ids)} accessible PDFs")
        
        # Try similarity search with error handling
        try:
            # Enhanced search with MMR for diversity if configured
            if QUERY_CONFIG.get("use_mmr", False) and hasattr(vector_store, 'max_marginal_relevance_search_with_score'):
                results = vector_store.max_marginal_relevance_search_with_score(
                    query_request.question,
                    k=RETRIEVAL_K,
                    fetch_k=RETRIEVAL_K * 2,
                    lambda_mult=QUERY_CONFIG.get("mmr_lambda", 0.5),
                    filter={"pdf_id": {"$in": accessible_pdf_ids}}
                )
            else:
                # Fallback to standard similarity search
                results = vector_store.similarity_search_with_score(
                    query_request.question,
                    k=RETRIEVAL_K,
                    filter={"pdf_id": {"$in": accessible_pdf_ids}}
                )
        except Exception as e:
            print(f"ERROR in vector search: {e}")
            # Try without filter as fallback
            try:
                results = vector_store.similarity_search_with_score(
                    query_request.question,
                    k=RETRIEVAL_K
                )
                # Manual filtering
                results = [(doc, score) for doc, score in results 
                          if doc.metadata.get('pdf_id') in accessible_pdf_ids]
            except Exception as e2:
                print(f"ERROR in fallback search: {e2}")
                return QueryResponse(
                    answer="Unable to search the documents. The vector database may need to be rebuilt. Please try again later or contact support.",
                    sources=[],
                    response_time=time.time() - start_time,
                    confidence=0.0
                )
        
        if not results:
            return QueryResponse(
                answer="No relevant information found in the accessible PDFs for your question. Try rephrasing your question or ensure the PDFs contain relevant information.",
                sources=[],
                response_time=time.time() - start_time,
                confidence=0.0
            )
        
        print(f"Found {len(results)} results")
        
        # Filter by similarity threshold
        filtered_results = [
            (doc, score) for doc, score in results 
            if score <= (1 - SIMILARITY_THRESHOLD)
        ]
        
        if not filtered_results:
            # Use all results if none meet threshold
            filtered_results = results[:3]
        
        # Prepare context
        context = prepare_context(
            filtered_results, 
            max_length=QUERY_CONFIG.get("max_context_length", 4000)
        )
        
        print(f"Context length: {len(context)} characters")
        
        # Generate answer with error handling
        try:
            response = chain.invoke({
                "question": query_request.question,
                "context": context
            })
        except Exception as e:
            print(f"ERROR generating answer: {e}")
            # Try with simpler prompt
            try:
                response = llm.invoke(f"Based on this context:\n{context[:2000]}\n\nAnswer: {query_request.question}")
            except:
                return QueryResponse(
                    answer="Unable to generate an answer. The language model may be unavailable. Please try again later.",
                    sources=[],
                    response_time=time.time() - start_time,
                    confidence=0.0
                )
        
        # Calculate confidence
        avg_score = sum(score for _, score in filtered_results[:3]) / min(3, len(filtered_results))
        confidence = max(0.0, min(1.0, 1 - avg_score))
        
        # Extract sources
        sources = []
        seen_sources = set()
        for doc, score in filtered_results[:5]:
            metadata = doc.metadata
            source_key = f"{metadata.get('filename', 'Unknown')}_{metadata.get('page', 0)}"
            
            if source_key not in seen_sources:
                sources.append({
                    "filename": metadata.get('filename', 'Unknown'),
                    "page": metadata.get('page', 0),
                    "score": float(1 - score),
                    "excerpt": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
                seen_sources.add(source_key)
        
        response_time = time.time() - start_time
        
        # Log query
        try:
            cursor.execute('''
                INSERT INTO query_logs (user_id, question, answer, sources, response_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (current_user['id'], query_request.question, response, 
                  json.dumps(sources), response_time))
            conn.commit()
        except Exception as e:
            print(f"Warning: Could not log query: {e}")
        
        return QueryResponse(
            answer=response,
            sources=sources,
            response_time=response_time,
            confidence=confidence
        )
        
    except Exception as e:
        print(f"ERROR in query processing: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return QueryResponse(
            answer=f"An error occurred while processing your query. Please try again or contact support if the problem persists.",
            sources=[],
            response_time=time.time() - start_time,
            confidence=0.0
        )
    finally:
        conn.close()

@router.post("/query/advanced")
async def advanced_query(
    query_request: QueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Advanced query with multiple retrieval strategies"""
    if not vector_store or not chain:
        raise HTTPException(status_code=500, detail="System not properly initialized")
    
    start_time = time.time()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get accessible PDFs
        if current_user['role'] == 'admin':
            cursor.execute('SELECT id, filename FROM pdfs WHERE processing_status = "completed"')
        else:
            cursor.execute('''
                SELECT id, filename FROM pdfs 
                WHERE processing_status = "completed" 
                AND (user_id = ? OR visibility = "public")
            ''', (current_user['id'],))
        
        accessible_pdfs = cursor.fetchall()
        accessible_pdf_ids = [pdf['id'] for pdf in accessible_pdfs]
        
        if not accessible_pdf_ids:
            return {
                "answer": "No accessible PDFs found.",
                "sources": [],
                "strategies_used": []
            }
        
        # Try multiple retrieval strategies
        all_results = []
        strategies_used = []
        
        # Strategy 1: Direct similarity search
        try:
            direct_results = vector_store.similarity_search_with_score(
                query_request.question,
                k=5,
                filter={"pdf_id": {"$in": accessible_pdf_ids}}
            )
            all_results.extend(direct_results)
            strategies_used.append("direct_similarity")
        except:
            pass
        
        # Strategy 2: Keyword expansion
        try:
            keywords = query_request.question.lower().split()
            important_keywords = [k for k in keywords if len(k) > 3][:3]
            
            for keyword in important_keywords:
                keyword_results = vector_store.similarity_search_with_score(
                    keyword,
                    k=2,
                    filter={"pdf_id": {"$in": accessible_pdf_ids}}
                )
                all_results.extend(keyword_results)
            strategies_used.append("keyword_expansion")
        except:
            pass
        
        # Strategy 3: Semantic expansion with question variations
        try:
            question_variation = f"Information about {query_request.question}"
            semantic_results = vector_store.similarity_search_with_score(
                question_variation,
                k=3,
                filter={"pdf_id": {"$in": accessible_pdf_ids}}
            )
            all_results.extend(semantic_results)
            strategies_used.append("semantic_expansion")
        except:
            pass
        
        # Deduplicate and rank results
        unique_results = {}
        for doc, score in all_results:
            content_key = hash(doc.page_content[:200])
            if content_key not in unique_results or score < unique_results[content_key][1]:
                unique_results[content_key] = (doc, score)
        
        # Sort by score
        ranked_results = sorted(unique_results.values(), key=lambda x: x[1])[:RETRIEVAL_K]
        
        if not ranked_results:
            return {
                "answer": "Could not find relevant information using multiple strategies.",
                "sources": [],
                "strategies_used": strategies_used
            }
        
        # Prepare comprehensive context
        context = prepare_context(ranked_results)
        
        # Generate comprehensive answer
        response = chain.invoke({
            "question": query_request.question,
            "context": context
        })
        
        # Extract sources
        sources = []
        for doc, score in ranked_results[:5]:
            metadata = doc.metadata
            sources.append({
                "filename": metadata.get('filename', 'Unknown'),
                "page": metadata.get('page', 0),
                "relevance": float(1 - score)
            })
        
        return {
            "answer": response,
            "sources": sources,
            "strategies_used": strategies_used,
            "response_time": time.time() - start_time
        }
        
    finally:
        conn.close()

@router.get("/query-history")
async def get_query_history(current_user: dict = Depends(get_current_user)):
    """Get query history for the current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if current_user['role'] == 'admin':
            cursor.execute('''
                SELECT q.*, u.username
                FROM query_logs q
                JOIN users u ON q.user_id = u.id
                ORDER BY q.created_at DESC
                LIMIT 50
            ''')
        else:
            cursor.execute('''
                SELECT * FROM query_logs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            ''', (current_user['id'],))
        
        queries = []
        for row in cursor.fetchall():
            query_dict = dict(row)
            if query_dict.get('sources'):
                query_dict['sources'] = json.loads(query_dict['sources'])
            queries.append(query_dict)
        
        return {"queries": queries}
        
    finally:
        conn.close()