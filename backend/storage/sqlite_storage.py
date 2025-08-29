# storage/sqlite_storage.py
import sqlite3
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import threading
import os

class SQLiteStorage:
    """Thread-safe SQLite storage for PDF files and metadata"""
    
    def __init__(self, db_path: str = None, storage_dir: str = None):
        # Use paths relative to backend folder
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pdf_storage.db")
        if storage_dir is None:
            storage_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pdf_files")
            
        self.db_path = db_path
        self.storage_dir = Path(storage_dir)
        
        # Create directories
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Database path: {self.db_path}")
        print(f"Storage directory: {self.storage_dir}")
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Initialize database
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Get thread-safe database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        try:
            yield self._local.conn
        except Exception as e:
            self._local.conn.rollback()
            raise e
    
    def _init_db(self):
        """Initialize SQLite database with tables"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Main PDFs table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pdfs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT UNIQUE NOT NULL,
                    file_size INTEGER NOT NULL,
                    page_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    user_id TEXT DEFAULT 'default',
                    upload_date TEXT NOT NULL,
                    processing_status TEXT DEFAULT 'pending',
                    processing_error TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Embeddings tracking table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pdf_id INTEGER NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_hash TEXT NOT NULL,
                    embedding_model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pdf_id) REFERENCES pdfs (id) ON DELETE CASCADE,
                    UNIQUE(pdf_id, page_number, chunk_index)
                )
            ''')
            
            # Query history table (optional, for analytics)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT,
                    sources TEXT,
                    response_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_pdfs_user_id ON pdfs(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_pdfs_file_hash ON pdfs(file_hash)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_pdfs_status ON pdfs(processing_status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_embeddings_pdf_id ON embeddings(pdf_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_query_user_id ON query_history(user_id)')
            
            conn.commit()
            print("Database initialized successfully")
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise
        finally:
            conn.close()
    
    async def save_pdf(self, file_content: bytes, filename: str, user_id: str = "default") -> Dict[str, Any]:
        """Save PDF file and create database entry"""
        try:
            # Calculate file hash for deduplication
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            with self.get_connection() as conn:
                # Check if file already exists
                existing = conn.execute(
                    "SELECT id, original_filename FROM pdfs WHERE file_hash = ? AND user_id = ?", 
                    (file_hash, user_id)
                ).fetchone()
                
                if existing:
                    return {
                        "success": False,
                        "message": f"This file has already been uploaded as '{existing['original_filename']}'",
                        "pdf_id": existing['id']
                    }
                
                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
                stored_filename = f"{timestamp}_{file_hash[:8]}_{safe_filename}"
                file_path = self.storage_dir / stored_filename
                
                # Save file to disk
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                # Save metadata to database
                cursor = conn.execute('''
                    INSERT INTO pdfs (
                        filename, original_filename, file_path, file_hash, 
                        file_size, user_id, upload_date, processing_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    stored_filename,
                    filename,
                    str(file_path),
                    file_hash,
                    len(file_content),
                    user_id,
                    datetime.now().isoformat(),
                    'pending'
                ))
                
                pdf_id = cursor.lastrowid
                conn.commit()
                
                print(f"PDF saved: ID={pdf_id}, File={filename}")
                
                return {
                    "success": True,
                    "message": "PDF uploaded successfully",
                    "pdf_id": pdf_id,
                    "filename": filename,
                    "file_size": len(file_content)
                }
                
        except Exception as e:
            print(f"Error saving PDF: {e}")
            return {
                "success": False,
                "message": f"Error saving PDF: {str(e)}"
            }
    
    async def get_pdf(self, pdf_id: int, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get PDF metadata"""
        with self.get_connection() as conn:
            query = "SELECT * FROM pdfs WHERE id = ?"
            params = [pdf_id]
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            row = conn.execute(query, params).fetchone()
            
            if row:
                result = dict(row)
                # Parse JSON metadata
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except:
                        result['metadata'] = {}
                return result
        return None
    
    async def get_pdf_content(self, pdf_id: int, user_id: Optional[str] = None) -> Optional[bytes]:
        """Get PDF file content"""
        pdf_info = await self.get_pdf(pdf_id, user_id)
        if pdf_info and pdf_info.get('file_path'):
            file_path = Path(pdf_info['file_path'])
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    return f.read()
        return None
    
    async def list_pdfs(self, user_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """List PDFs for a user with pagination"""
        with self.get_connection() as conn:
            # Get total count
            total = conn.execute(
                "SELECT COUNT(*) as count FROM pdfs WHERE user_id = ?",
                (user_id,)
            ).fetchone()['count']
            
            # Get paginated results
            rows = conn.execute('''
                SELECT id, original_filename as filename, file_size, page_count, 
                       chunk_count, upload_date, processing_status, created_at
                FROM pdfs 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (user_id, limit, offset)).fetchall()
            
            pdfs = [dict(row) for row in rows]
            
            print(f"Found {len(pdfs)} PDFs for user {user_id}")
            
            return {
                "pdfs": pdfs,
                "total": total,
                "limit": limit,
                "offset": offset
            }
    
    async def update_pdf_status(self, pdf_id: int, status: str, 
                               page_count: Optional[int] = None,
                               chunk_count: Optional[int] = None,
                               error: Optional[str] = None) -> bool:
        """Update PDF processing status"""
        with self.get_connection() as conn:
            updates = ["processing_status = ?", "updated_at = ?"]
            values = [status, datetime.now().isoformat()]
            
            if page_count is not None:
                updates.append("page_count = ?")
                values.append(page_count)
            
            if chunk_count is not None:
                updates.append("chunk_count = ?")
                values.append(chunk_count)
            
            if error:
                updates.append("processing_error = ?")
                values.append(error)
            
            values.append(pdf_id)
            
            conn.execute(
                f"UPDATE pdfs SET {', '.join(updates)} WHERE id = ?",
                values
            )
            conn.commit()
            
            print(f"Updated PDF {pdf_id} status to {status}")
            return True
    
    async def delete_pdf(self, pdf_id: int, user_id: str) -> Dict[str, Any]:
        """Delete PDF file and all related data"""
        try:
            with self.get_connection() as conn:
                # Get file info
                pdf = conn.execute(
                    "SELECT file_path FROM pdfs WHERE id = ? AND user_id = ?",
                    (pdf_id, user_id)
                ).fetchone()
                
                if not pdf:
                    return {"success": False, "message": "PDF not found"}
                
                # Delete file from disk
                file_path = Path(pdf['file_path'])
                if file_path.exists():
                    file_path.unlink()
                    print(f"Deleted file: {file_path}")
                
                # Delete from database (embeddings cascade delete)
                conn.execute("DELETE FROM pdfs WHERE id = ?", (pdf_id,))
                conn.commit()
                
                print(f"Deleted PDF {pdf_id} from database")
                return {"success": True, "message": "PDF deleted successfully"}
                
        except Exception as e:
            print(f"Error deleting PDF: {e}")
            return {"success": False, "message": f"Error deleting PDF: {str(e)}"}
    
    async def save_embedding_info(self, pdf_id: int, page_number: int, 
                                 chunk_index: int, chunk_text: str,
                                 model: str = "mxbai-embed-large") -> bool:
        """Save embedding information"""
        chunk_hash = hashlib.md5(chunk_text.encode()).hexdigest()
        
        with self.get_connection() as conn:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO embeddings 
                    (pdf_id, page_number, chunk_index, chunk_text, chunk_hash, embedding_model)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (pdf_id, page_number, chunk_index, chunk_text[:500], chunk_hash, model))
                conn.commit()
                return True
            except Exception as e:
                print(f"Error saving embedding info: {e}")
                return False
    
    async def save_query_history(self, user_id: str, question: str, 
                                answer: str, sources: List[Dict], 
                                response_time: float) -> bool:
        """Save query history for analytics"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO query_history (user_id, question, answer, sources, response_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, question, answer, json.dumps(sources), response_time))
            conn.commit()
            return True
    
    async def get_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        with self.get_connection() as conn:
            # PDF statistics
            pdf_stats = conn.execute('''
                SELECT 
                    COUNT(*) as total_pdfs,
                    COALESCE(SUM(file_size), 0) as total_size,
                    COALESCE(SUM(page_count), 0) as total_pages,
                    COALESCE(SUM(chunk_count), 0) as total_chunks,
                    COALESCE(AVG(file_size), 0) as avg_size
                FROM pdfs 
                WHERE user_id = ? AND processing_status = 'completed'
            ''', (user_id,)).fetchone()
            
            # Query statistics  
            query_stats = conn.execute('''
                SELECT 
                    COUNT(*) as total_queries,
                    AVG(response_time) as avg_response_time
                FROM query_history 
                WHERE user_id = ?
            ''', (user_id,)).fetchone()
            
            return {
                "pdf_count": pdf_stats['total_pdfs'] or 0,
                "total_size": pdf_stats['total_size'] or 0,
                "total_pages": pdf_stats['total_pages'] or 0,
                "total_chunks": pdf_stats['total_chunks'] or 0,
                "average_size": round(pdf_stats['avg_size'] or 0, 2),
                "total_queries": query_stats['total_queries'] or 0,
                "avg_response_time": round(query_stats['avg_response_time'] or 0, 2) if query_stats['avg_response_time'] else 0,
                "user_id": user_id
            }