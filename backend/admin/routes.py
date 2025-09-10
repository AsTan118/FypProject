# admin/routes.py - Fixed version with proper multi-file handling
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from database import get_db_connection
from auth.utils import get_current_user
import bcrypt
import os
import json
import time
import asyncio

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Admin authentication using the existing get_current_user
async def require_admin(current_user: dict = Depends(get_current_user)):
    """Ensure current user is admin"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.post("/upload-public")
async def upload_public_pdfs(
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(require_admin)
):
    """Upload multiple PDFs that all users can access (admin only)"""
    print(f"Admin upload from: {current_user['username']}")
    print(f"Files received: {len(files)} files")
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    results = []
    successful_uploads = []
    failed_uploads = []
    
    for file in files:
        try:
            # Validate file type
            if not file.filename or not file.filename.lower().endswith('.pdf'):
                result = {
                    "filename": file.filename,
                    "success": False,
                    "error": f"Only PDF files are allowed"
                }
                failed_uploads.append(result)
                results.append(result)
                continue
            
            # Process single file
            result = await process_single_pdf_upload(file, current_user, visibility='public')
            
            if result['success']:
                successful_uploads.append(result)
            else:
                failed_uploads.append(result)
            
            results.append(result)
            
        except Exception as e:
            print(f"Error processing file {file.filename}: {e}")
            result = {
                "filename": file.filename,
                "success": False,
                "error": str(e)
            }
            failed_uploads.append(result)
            results.append(result)
    
    return {
        "success": True,
        "message": f"Processed {len(files)} files: {len(successful_uploads)} successful, {len(failed_uploads)} failed",
        "results": results,
        "successful_count": len(successful_uploads),
        "failed_count": len(failed_uploads)
    }

async def process_single_pdf_upload(file: UploadFile, current_user: dict, visibility: str = 'public'):
    """Process a single PDF upload"""
    print(f"Processing file: {file.filename}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    file_path = None
    
    try:
        # Read file content
        content = await file.read()
        if not content:
            return {
                "filename": file.filename,
                "success": False,
                "error": "Empty file received"
            }
        
        print(f"File {file.filename} size: {len(content)} bytes")
        
        # Create directory
        os.makedirs("pdfs", exist_ok=True)
        
        # Generate unique filename
        import re
        import random
        timestamp = str(int(time.time() * 1000))
        random_suffix = str(random.randint(1000, 9999))
        safe_filename = re.sub(r'[^\w\-_\.]', '_', file.filename)
        unique_filename = f"{timestamp}_{random_suffix}_{safe_filename}"
        file_path = os.path.join("pdfs", f"admin_{current_user['id']}_{unique_filename}")
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        print(f"File saved to: {file_path}")
        
        # Insert into database with public visibility
        cursor.execute('''
            INSERT INTO pdfs (user_id, filename, file_path, file_size, visibility, processing_status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (current_user['id'], file.filename, file_path, len(content), visibility, 'processing'))
        
        pdf_id = cursor.lastrowid
        conn.commit()
        
        print(f"PDF record created with ID: {pdf_id} for file: {file.filename}")
        
        # Schedule background processing without waiting
        try:
            from pdf.routes import schedule_pdf_processing
            asyncio.create_task(schedule_pdf_processing(pdf_id, file_path))
            print(f"Background processing scheduled for PDF {pdf_id}")
        except Exception as e:
            print(f"Warning: Could not start background processing: {e}")
            # Don't fail the upload if processing can't start
        
        return {
            "filename": file.filename,
            "success": True,
            "pdf_id": pdf_id,
            "message": f"Successfully uploaded {file.filename}"
        }
        
    except Exception as e:
        print(f"Upload error for {file.filename}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Cleanup on error
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        if 'conn' in locals():
            conn.rollback()
        
        return {
            "filename": file.filename,
            "success": False,
            "error": str(e)
        }
    finally:
        if 'conn' in locals():
            conn.close()

# Stats endpoint
@router.get("/stats")
async def get_system_stats(admin_user: dict = Depends(require_admin)):
    """Get system statistics (admin only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        stats = {}
        
        # Get user counts
        cursor.execute("SELECT COUNT(*) as total FROM users")
        result = cursor.fetchone()
        stats['total_users'] = result['total'] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'admin'")
        result = cursor.fetchone()
        stats['admin_users'] = result['total'] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'student'")
        result = cursor.fetchone()
        stats['student_users'] = result['total'] if result else 0
        
        # Get PDF counts
        cursor.execute("SELECT COUNT(*) as total FROM pdfs")
        result = cursor.fetchone()
        stats['total_pdfs'] = result['total'] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM pdfs WHERE visibility = 'public'")
        result = cursor.fetchone()
        stats['public_pdfs'] = result['total'] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM pdfs WHERE visibility = 'private'")
        result = cursor.fetchone()
        stats['private_pdfs'] = result['total'] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM pdfs WHERE processing_status = 'completed'")
        result = cursor.fetchone()
        stats['processed_pdfs'] = result['total'] if result else 0
        
        # Get query count
        cursor.execute("SELECT COUNT(*) as total FROM query_logs")
        result = cursor.fetchone()
        stats['total_queries'] = result['total'] if result else 0
        
        # Get recent queries
        cursor.execute('''
            SELECT q.question, q.created_at, u.username
            FROM query_logs q
            JOIN users u ON q.user_id = u.id
            ORDER BY q.created_at DESC
            LIMIT 10
        ''')
        
        recent_queries = []
        for row in cursor.fetchall():
            recent_queries.append({
                'username': row['username'],
                'question': row['question'],
                'created_at': row['created_at']
            })
        
        stats['avg_response_time'] = 0
        stats['recent_queries'] = recent_queries
        
        return stats
        
    finally:
        conn.close()

@router.get("/users")
async def get_all_users(admin_user: dict = Depends(require_admin)):
    """Get all users (admin only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, username, email, full_name, role, created_at
            FROM users
            ORDER BY created_at DESC
        ''')
        users = [dict(row) for row in cursor.fetchall()]
        return {"users": users}
    finally:
        conn.close()

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: dict = Depends(require_admin)
):
    """Delete a user (admin only)"""
    if user_id == admin_user['id']:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete user's PDFs files from disk
        cursor.execute('SELECT file_path FROM pdfs WHERE user_id = ?', (user_id,))
        pdf_files = cursor.fetchall()
        
        for pdf in pdf_files:
            if pdf['file_path'] and os.path.exists(pdf['file_path']):
                try:
                    os.remove(pdf['file_path'])
                except:
                    pass
        
        # Delete user (cascade will handle related records)
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        
        return {
            "success": True,
            "message": f"User {user['username']} deleted successfully"
        }
    finally:
        conn.close()

@router.get("/pdfs")
async def get_all_pdfs(admin_user: dict = Depends(require_admin)):
    """Get all PDFs in the system (admin only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT p.*, u.username as owner_username
            FROM pdfs p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.uploaded_at DESC
        ''')
        
        pdfs = [dict(row) for row in cursor.fetchall()]
        
        return {
            "pdfs": pdfs,
            "total": len(pdfs),
            "public": sum(1 for p in pdfs if p.get('visibility') == 'public'),
            "private": sum(1 for p in pdfs if p.get('visibility') == 'private')
        }
    finally:
        conn.close()

@router.put("/pdfs/{pdf_id}/visibility")
async def update_pdf_visibility(
    pdf_id: int,
    visibility: str = Form(...),
    admin_user: dict = Depends(require_admin)
):
    """Update PDF visibility (admin only)"""
    if visibility not in ['public', 'private']:
        raise HTTPException(status_code=400, detail="Visibility must be 'public' or 'private'")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE pdfs SET visibility = ? WHERE id = ?
        ''', (visibility, pdf_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="PDF not found")
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"PDF visibility updated to {visibility}"
        }
    finally:
        conn.close()