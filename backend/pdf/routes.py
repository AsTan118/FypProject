# pdf/routes.py - Fixed version with improved async processing
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from auth.utils import get_current_user
from database import get_db_connection
import os
import json
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import random

router = APIRouter(prefix="/api", tags=["PDFs"])

# Global variables
vector_store = None
processing_executor = ThreadPoolExecutor(max_workers=4)
processing_tasks = {}

def set_vector_store(vs):
    """Set the vector store instance"""
    global vector_store
    vector_store = vs

def process_pdf_in_thread(pdf_id: int, file_path: str):
    """Process PDF in a separate thread to avoid blocking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print(f"Starting processing for PDF {pdf_id}")
        
        # Import processor
        from pdf.processor import PDFProcessor
        processor = PDFProcessor(chunk_size=1000, chunk_overlap=200)
        
        # Extract text from PDF
        try:
            text_chunks, page_count = processor.extract_text_from_pdf(file_path)
            print(f"Extracted {len(text_chunks)} chunks from {page_count} pages")
        except Exception as e:
            print(f"Error extracting text from PDF {pdf_id}: {e}")
            text_chunks, page_count = [], 0
        
        if not text_chunks:
            print(f"No text extracted from PDF {pdf_id}, marking as completed")
            cursor.execute('''
                UPDATE pdfs 
                SET processing_status = 'completed', 
                    page_count = 0,
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (pdf_id,))
            conn.commit()
            return
        
        # Update page count
        cursor.execute('UPDATE pdfs SET page_count = ? WHERE id = ?', (page_count, pdf_id))
        
        # Insert chunks in batch
        chunk_data = []
        for i, chunk in enumerate(text_chunks):
            chunk_data.append((
                pdf_id, i, chunk['content'], 
                chunk['page'], json.dumps(chunk['metadata'])
            ))
        
        # Insert all chunks at once
        cursor.executemany('''
            INSERT INTO pdf_chunks (pdf_id, chunk_index, content, page_number, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', chunk_data)
        
        # Try to add to vector store if available
        if vector_store and text_chunks:
            try:
                texts = [chunk['content'] for chunk in text_chunks]
                metadatas = [
                    {**chunk['metadata'], 'pdf_id': pdf_id}
                    for chunk in text_chunks
                ]
                
                # Add in smaller batches to avoid timeout
                batch_size = 10
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i+batch_size]
                    batch_meta = metadatas[i:i+batch_size]
                    try:
                        vector_store.add_texts(texts=batch_texts, metadatas=batch_meta)
                    except Exception as e:
                        print(f"Warning: Could not add batch to vector store: {e}")
                
                print(f"Added {len(texts)} chunks to vector store for PDF {pdf_id}")
            except Exception as e:
                print(f"Warning: Could not add to vector store: {e}")
                # Don't fail the whole process
        
        # Mark as completed
        cursor.execute('''
            UPDATE pdfs 
            SET processing_status = 'completed', 
                processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (pdf_id,))
        
        conn.commit()
        print(f"Successfully completed processing PDF {pdf_id}")
        
    except Exception as e:
        print(f"Error processing PDF {pdf_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Mark as completed even on error to avoid stuck state
        try:
            cursor.execute('''
                UPDATE pdfs 
                SET processing_status = 'completed', 
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (pdf_id,))
            conn.commit()
        except:
            pass
    finally:
        # Remove from processing tasks
        if pdf_id in processing_tasks:
            del processing_tasks[pdf_id]
        conn.close()

async def schedule_pdf_processing(pdf_id: int, file_path: str):
    """Schedule PDF processing without blocking"""
    # Check if already processing
    if pdf_id in processing_tasks:
        print(f"PDF {pdf_id} is already being processed")
        return
    
    # Submit to executor
    future = processing_executor.submit(process_pdf_in_thread, pdf_id, file_path)
    processing_tasks[pdf_id] = future
    print(f"Scheduled processing for PDF {pdf_id}")

@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a PDF file"""
    print(f"Upload request from user: {current_user['username']} (role: {current_user['role']})")
    
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    file_path = None
    
    try:
        # Create pdfs directory
        os.makedirs("pdfs", exist_ok=True)
        
        # Generate unique filename
        import re
        timestamp = str(int(time.time() * 1000))
        random_suffix = str(random.randint(1000, 9999))
        safe_filename = re.sub(r'[^\w\-_\.]', '_', file.filename)
        unique_filename = f"{timestamp}_{random_suffix}_{safe_filename}"
        file_path = os.path.join("pdfs", f"user_{current_user['id']}_{unique_filename}")
        
        # Read and save file
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file received")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        print(f"File saved to: {file_path}")
        
        # Set visibility (private for all users by default)
        visibility = 'private'
        
        # Insert PDF record
        cursor.execute('''
            INSERT INTO pdfs (user_id, filename, file_path, file_size, visibility, processing_status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (current_user['id'], file.filename, file_path, len(content), visibility, 'processing'))
        
        pdf_id = cursor.lastrowid
        conn.commit()
        
        print(f"PDF record created with ID: {pdf_id}")
        
        # Schedule background processing
        await schedule_pdf_processing(pdf_id, file_path)
        
        return {
            "success": True,
            "message": f"PDF '{file.filename}' uploaded successfully and is being processed",
            "pdf_id": pdf_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {str(e)}")
        
        # Cleanup on error
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        if 'conn' in locals():
            conn.rollback()
        
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/pdfs")
async def get_pdfs(current_user: dict = Depends(get_current_user)):
    """Get PDFs accessible to the current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if current_user['role'] == 'admin':
            # Admins can see all PDFs
            cursor.execute('''
                SELECT p.*, u.username as owner_username
                FROM pdfs p
                JOIN users u ON p.user_id = u.id
                ORDER BY p.uploaded_at DESC
            ''')
        else:
            # Students can see their own PDFs and public PDFs
            cursor.execute('''
                SELECT p.*, u.username as owner_username
                FROM pdfs p
                JOIN users u ON p.user_id = u.id
                WHERE p.user_id = ? OR p.visibility = 'public'
                ORDER BY p.uploaded_at DESC
            ''', (current_user['id'],))
        
        pdfs = []
        for row in cursor.fetchall():
            pdf_dict = dict(row)
            pdf_dict['is_owner'] = pdf_dict['user_id'] == current_user['id']
            pdfs.append(pdf_dict)
        
        return {"pdfs": pdfs}
        
    finally:
        conn.close()

@router.delete("/pdfs/{pdf_id}")
async def delete_pdf(pdf_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a PDF"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT user_id, file_path FROM pdfs WHERE id = ?', (pdf_id,))
        pdf = cursor.fetchone()
        
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF not found")
        
        if current_user['role'] != 'admin' and pdf['user_id'] != current_user['id']:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Delete file from disk
        if pdf['file_path'] and os.path.exists(pdf['file_path']):
            try:
                os.remove(pdf['file_path'])
            except:
                pass
        
        # Delete from database (cascade will handle chunks)
        cursor.execute('DELETE FROM pdfs WHERE id = ?', (pdf_id,))
        conn.commit()
        
        # Remove from processing tasks if still processing
        if pdf_id in processing_tasks:
            del processing_tasks[pdf_id]
        
        return {"success": True, "message": "PDF deleted successfully"}
        
    finally:
        conn.close()

@router.get("/processing-status/{pdf_id}")
async def get_processing_status(pdf_id: int, current_user: dict = Depends(get_current_user)):
    """Get processing status of a PDF"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT processing_status, user_id, visibility 
            FROM pdfs WHERE id = ?
        ''', (pdf_id,))
        pdf = cursor.fetchone()
        
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF not found")
        
        if current_user['role'] != 'admin':
            if pdf['user_id'] != current_user['id'] and pdf['visibility'] != 'public':
                raise HTTPException(status_code=403, detail="Access denied")
        
        return {"status": pdf['processing_status']}
        
    finally:
        conn.close()

# Startup task to clean up stuck PDFs
async def cleanup_stuck_pdfs():
    """Clean up any PDFs stuck in processing state on startup"""
    await asyncio.sleep(3)  # Wait for system to initialize
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Find PDFs stuck in processing state
        cursor.execute('''
            SELECT id, file_path 
            FROM pdfs 
            WHERE processing_status = 'processing'
            AND datetime(uploaded_at) < datetime('now', '-2 minutes')
        ''')
        
        stuck_pdfs = cursor.fetchall()
        
        for pdf in stuck_pdfs:
            print(f"Reprocessing stuck PDF {pdf['id']}")
            await schedule_pdf_processing(pdf['id'], pdf['file_path'])
        
        if stuck_pdfs:
            print(f"Scheduled reprocessing for {len(stuck_pdfs)} stuck PDFs")
    
    except Exception as e:
        print(f"Error in cleanup_stuck_pdfs: {e}")
    finally:
        conn.close()

# Export for backward compatibility
async def process_pdf_background(pdf_id: int, file_path: str):
    """Wrapper for backward compatibility"""
    await schedule_pdf_processing(pdf_id, file_path)

async def process_pdf_background_fast(pdf_id: int, file_path: str):
    """Wrapper for backward compatibility"""
    await schedule_pdf_processing(pdf_id, file_path)