# pdf/routes.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict
from datetime import datetime
from pathlib import Path
import hashlib
import asyncio
from database import get_db
from auth.utils import verify_token
from pdf.processor import process_pdf_async
from config import MAX_FILE_SIZE, PDF_FILES_PATH

router = APIRouter(prefix="/api", tags=["pdfs"])

# This will be set by main.py
vector_store = None

def set_vector_store(store):
    """Set vector store from main.py"""
    global vector_store
    vector_store = store

@router.get("/pdfs")
async def list_pdfs(current_user: Dict = Depends(verify_token)):
    """List all PDFs for current user"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, original_filename as filename, file_size, page_count, 
                   chunk_count, upload_date, processing_status, created_at
            FROM pdfs 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (current_user['user_id'],))
        
        pdfs = [dict(row) for row in cursor.fetchall()]
        return {"pdfs": pdfs, "total": len(pdfs)}

@router.post("/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: Dict = Depends(verify_token)
):
    """Upload a PDF file (protected)"""
    print(f"Uploading: {file.filename} for user: {current_user['username']}")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    contents = await file.read()
    
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB")
    
    file_hash = hashlib.sha256(contents).hexdigest()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check for duplicates for this user
        cursor.execute(
            "SELECT id FROM pdfs WHERE file_hash = ? AND user_id = ?",
            (file_hash, current_user['user_id'])
        )
        existing = cursor.fetchone()
        
        if existing:
            return {
                "success": False,
                "message": "This file has already been uploaded",
                "pdf_id": existing[0]
            }
        
        # Save file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
        stored_filename = f"{current_user['user_id']}_{timestamp}_{safe_filename}"
        file_path = Path(PDF_FILES_PATH) / stored_filename
        
        with open(file_path, 'wb') as f:
            f.write(contents)
        
        # Insert into database
        cursor.execute('''
            INSERT INTO pdfs (
                filename, original_filename, file_path, file_hash, 
                file_size, user_id, upload_date, processing_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'processing')
        ''', (
            stored_filename,
            file.filename,
            str(file_path),
            file_hash,
            len(contents),
            current_user['user_id'],
            datetime.now().isoformat()
        ))
        
        pdf_id = cursor.lastrowid
        conn.commit()
        
        # Process PDF in background
        background_tasks.add_task(
            process_pdf_async,
            pdf_id,
            contents,
            file.filename,
            current_user['user_id'],
            vector_store
        )
        
        return {
            "success": True,
            "message": "PDF uploaded successfully. Processing in background...",
            "pdf_id": pdf_id,
            "filename": file.filename
        }

@router.delete("/pdfs/{pdf_id}")
async def delete_pdf(pdf_id: int, current_user: Dict = Depends(verify_token)):
    """Delete a PDF (protected)"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get file path and verify ownership
        cursor.execute(
            "SELECT file_path FROM pdfs WHERE id = ? AND user_id = ?",
            (pdf_id, current_user['user_id'])
        )
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="PDF not found")
        
        # Delete file from disk
        file_path = Path(result['file_path'])
        if file_path.exists():
            file_path.unlink()
        
        # Delete from database
        cursor.execute("DELETE FROM pdfs WHERE id = ?", (pdf_id,))
        cursor.execute("DELETE FROM embeddings_metadata WHERE pdf_id = ?", (pdf_id,))
        conn.commit()
        
        return {"success": True, "message": "PDF deleted successfully"}

@router.get("/processing-status/{pdf_id}")
async def get_processing_status(
    pdf_id: int,
    current_user: Dict = Depends(verify_token)
):
    """Get PDF processing status (protected)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM pdfs WHERE id = ? AND user_id = ?",
            (pdf_id, current_user['user_id'])
        )
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="PDF not found")
        
        return {
            "pdf_id": pdf_id,
            "filename": result["original_filename"],
            "status": result["processing_status"],
            "page_count": result["page_count"],
            "chunk_count": result["chunk_count"],
            "error": result["processing_error"]
        }

@router.get("/processing-events/{pdf_id}")
async def processing_events(pdf_id: int):
    """Stream PDF processing status (SSE)"""
    async def event_generator():
        last_status = None
        while True:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT processing_status FROM pdfs WHERE id = ?", (pdf_id,))
                row = cursor.fetchone()
                
                if row:
                    status = row['processing_status']
                    if status != last_status:
                        yield f"data: {status}\n\n"
                        last_status = status
                    
                    if status in ["completed", "failed"]:
                        break
            
            await asyncio.sleep(2)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")