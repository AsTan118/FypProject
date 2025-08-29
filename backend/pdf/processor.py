# pdf/processor.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from langchain_core.documents import Document
from database import get_db
from pdf.utils import extract_text_from_pdf

executor = ThreadPoolExecutor(max_workers=4)

async def process_pdf_async(pdf_id: int, pdf_content: bytes, filename: str, user_id: int, vector_store):
    """Process PDF asynchronously"""
    loop = asyncio.get_event_loop()
    
    try:
        chunks = await loop.run_in_executor(executor, extract_text_from_pdf, pdf_content)
        
        if not chunks:
            raise Exception("No readable text content found in PDF")
        
        documents = []
        chunk_metadata = []
        
        for chunk_data in chunks:
            chunk_id = f"{pdf_id}_{chunk_data['page']}_{chunk_data['chunk']}"
            
            doc = Document(
                page_content=chunk_data["text"],
                metadata={
                    "pdf_id": pdf_id,
                    "filename": filename,
                    "page": chunk_data["page"],
                    "chunk": chunk_data["chunk"],
                    "chunk_id": chunk_id,
                    "user_id": user_id
                }
            )
            documents.append(doc)
            
            chunk_metadata.append({
                "pdf_id": pdf_id,
                "chunk_id": chunk_id,
                "page": chunk_data["page"],
                "chunk": chunk_data["chunk"],
                "text": chunk_data["text"][:500]
            })
        
        await loop.run_in_executor(
            executor,
            lambda: vector_store.add_documents(documents)
        )
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            for meta in chunk_metadata:
                cursor.execute('''
                    INSERT INTO embeddings_metadata 
                    (pdf_id, chunk_id, page_number, chunk_index, chunk_text)
                    VALUES (?, ?, ?, ?, ?)
                ''', (meta["pdf_id"], meta["chunk_id"], meta["page"], meta["chunk"], meta["text"]))
            
            page_count = max(chunk["page"] for chunk in chunks)
            cursor.execute(
                "UPDATE pdfs SET processing_status = 'completed', page_count = ?, chunk_count = ? WHERE id = ?",
                (page_count, len(chunks), pdf_id)
            )
            conn.commit()
        
        print(f"PDF {pdf_id} processed: {page_count} pages, {len(chunks)} chunks")
        
    except Exception as e:
        print(f"Error processing PDF {pdf_id}: {e}")
        with get_db() as conn:
            conn.execute(
                "UPDATE pdfs SET processing_status = 'failed', processing_error = ? WHERE id = ?",
                (str(e), pdf_id)
            )
            conn.commit()