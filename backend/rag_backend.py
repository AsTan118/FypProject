# enhanced_backend_with_auth.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import uvicorn
import pdfplumber
import io
import time
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
import jwt
import bcrypt
from contextlib import contextmanager

# LangChain imports
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI(title="Enhanced PDF RAG System with Auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SECRET_KEY = "your-secret-key-change-this-in-production"  # Change this!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Create directories
Path("../data").mkdir(exist_ok=True)
Path("../data/pdf_files").mkdir(exist_ok=True)
Path("../data/chroma_db").mkdir(exist_ok=True)

DB_PATH = "../data/pdf_storage.db"
CHROMA_PATH = "../data/chroma_db"

# Security
security = HTTPBearer()

# Thread pool for CPU-intensive operations
executor = ThreadPoolExecutor(max_workers=4)

# Initialize Ollama components
print("Initializing Ollama components...")
embeddings = OllamaEmbeddings(model="mxbai-embed-large")
llm = OllamaLLM(
    model="llama3.2",
    temperature=0.2,
    top_p=0.9,
    num_ctx=4096,
    num_predict=512,
)

vector_store = Chroma(
    collection_name="pdf_documents",
    persist_directory=CHROMA_PATH,
    embedding_function=embeddings
)

prompt_template = """
You are an expert in answering questions about university information.

Here are some relevant excerpts from uploaded documents:
{context}

Question: {question}

Please provide a clear, helpful, and concise answer.
- Focus on summarizing what the documents say
- If the exact answer is not found, provide the closest related information
- Do not invent facts outside the documents
"""

prompt = ChatPromptTemplate.from_template(prompt_template)
chain = prompt | llm

# Database context manager
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """Initialize SQLite database with all required tables"""
    conn = sqlite3.connect(DB_PATH)
    
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # PDFs table with user relationship
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pdfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0,
            user_id INTEGER NOT NULL,
            upload_date TEXT NOT NULL,
            processing_status TEXT DEFAULT 'pending',
            processing_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(file_hash, user_id)
        )
    ''')
    
    # Embeddings metadata
    conn.execute('''
        CREATE TABLE IF NOT EXISTS embeddings_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_id INTEGER NOT NULL,
            chunk_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pdf_id) REFERENCES pdfs (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

init_database()

# Pydantic models
class UserSignup(BaseModel):
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')

# Helper functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    """Create a JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Verify JWT token and return user data"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        username = payload.get("username")
        
        if user_id is None or username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"user_id": user_id, "username": username}
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Auth endpoints
@app.post("/api/auth/signup", response_model=Token)
async def signup(user: UserSignup):
    """Register a new user"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", 
                      (user.email, user.username))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists"
            )
        
        # Create user
        hashed_password = hash_password(user.password)
        cursor.execute('''
            INSERT INTO users (email, username, password_hash, full_name)
            VALUES (?, ?, ?, ?)
        ''', (user.email, user.username, hashed_password, user.full_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Create token
        access_token = create_access_token({
            "user_id": user_id,
            "username": user.username
        })
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name
            }
        }

@app.post("/api/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Login user and return token"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Find user by username or email
        cursor.execute('''
            SELECT id, username, email, password_hash, full_name, is_active
            FROM users 
            WHERE username = ? OR email = ?
        ''', (user_credentials.username, user_credentials.username))
        
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        if not user['is_active']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        # Verify password
        if not verify_password(user_credentials.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Update last login
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                      (datetime.utcnow(), user['id']))
        conn.commit()
        
        # Create token
        access_token = create_access_token({
            "user_id": user['id'],
            "username": user['username']
        })
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "full_name": user['full_name']
            }
        }

@app.get("/api/auth/me")
async def get_current_user(current_user: Dict = Depends(verify_token)):
    """Get current user info"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, full_name, created_at, last_login
            FROM users WHERE id = ?
        ''', (current_user['user_id'],))
        
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return dict(user)

# Protected PDF endpoints
@app.get("/api/pdfs")
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

@app.post("/api/upload")
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
    
    if len(contents) > 50 * 1024 * 1024:
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
                "pdf_id": existing['id']
            }
        
        # Save file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
        stored_filename = f"{current_user['user_id']}_{timestamp}_{safe_filename}"
        file_path = Path("../data/pdf_files") / stored_filename
        
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
            current_user['user_id']
        )
        
        return {
            "success": True,
            "message": "PDF uploaded successfully. Processing in background...",
            "pdf_id": pdf_id,
            "filename": file.filename
        }

@app.post("/api/query")
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

@app.delete("/api/pdfs/{pdf_id}")
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

@app.get("/api/processing-status/{pdf_id}")
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

@app.get("/api/processing-events/{pdf_id}")
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

# Keep existing PDF processing functions
def clean_text(text: str, page_num: int = None) -> str:
    """Clean extracted text from PDF"""
    if not text:
        return ""
    text = ' '.join(text.split())
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('™', "'").replace('œ', '"')
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if page_num == 1:
            cleaned_lines.append(line)
            continue
        
        if line.isdigit() or len(line) < 5 or not any(c.isalnum() for c in line):
            continue
        
        cleaned_lines.append(line)
    
    return ' '.join(cleaned_lines)

def extract_text_from_pdf(pdf_content: bytes) -> List[Dict[str, Any]]:
    """Extract text from PDF"""
    chunks = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                
                cleaned_text = clean_text(text, page_num=page_num)
                if not cleaned_text:
                    continue
                
                text_chunks = split_text_into_chunks(cleaned_text, chunk_size=1000, overlap=200)
                
                for chunk_index, chunk_text in enumerate(text_chunks):
                    if len(chunk_text) > 20:
                        chunks.append({
                            "page": page_num,
                            "chunk": chunk_index,
                            "text": chunk_text
                        })
    
    except Exception as e:
        print(f"Error extracting text: {e}")
        raise
    
    return chunks

def split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks"""
    if not text:
        return []
    
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence_size = len(sentence)
        
        if current_size + sentence_size > chunk_size and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(chunk_text)
            
            overlap_size = 0
            overlap_sentences = []
            for sent in reversed(current_chunk):
                overlap_size += len(sent)
                overlap_sentences.insert(0, sent)
                if overlap_size >= overlap:
                    break
            
            current_chunk = overlap_sentences
            current_size = sum(len(s) for s in current_chunk)
        
        current_chunk.append(sentence)
        current_size += sentence_size
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

async def process_pdf_async(pdf_id: int, pdf_content: bytes, filename: str, user_id: int):
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

if __name__ == "__main__":
    print("\n" + "="*70)
    print("PDF RAG SYSTEM WITH AUTHENTICATION")
    print("="*70)
    print("\n📋 SETUP INSTRUCTIONS:")
    print("1. Install requirements:")
    print("   pip install fastapi uvicorn pdfplumber")
    print("   pip install langchain-ollama langchain-chroma")
    print("   pip install pyjwt bcrypt python-multipart")
    print("\n2. Ensure Ollama is running with required models")
    print("\n3. IMPORTANT: Change SECRET_KEY in production!")
    print("\n🌐 SERVER:")
    print("Starting at: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
    username: str
    password: str
    full_name: Optional[str] = None
    
    @validator('email')
    def validate_email(cls, v):
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v.lower()

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

class QueryRequest(BaseModel):
    question: str

# Helper functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    """Create a JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Verify JWT token and return user data"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        username = payload.get("username")
        
        if user_id is None or username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"user_id": user_id, "username": username}
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Auth endpoints
@app.post("/api/auth/signup", response_model=Token)
async def signup(user: UserSignup):
    """Register a new user"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", 
                      (user.email, user.username))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists"
            )
        
        # Create user
        hashed_password = hash_password(user.password)
        cursor.execute('''
            INSERT INTO users (email, username, password_hash, full_name)
            VALUES (?, ?, ?, ?)
        ''', (user.email, user.username, hashed_password, user.full_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Create token
        access_token = create_access_token({
            "user_id": user_id,
            "username": user.username
        })
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name
            }
        }

@app.post("/api/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Login user and return token"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Find user by username or email
        cursor.execute('''
            SELECT id, username, email, password_hash, full_name, is_active
            FROM users 
            WHERE username = ? OR email = ?
        ''', (user_credentials.username, user_credentials.username))
        
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        if not user['is_active']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        # Verify password
        if not verify_password(user_credentials.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Update last login
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                      (datetime.utcnow(), user['id']))
        conn.commit()
        
        # Create token
        access_token = create_access_token({
            "user_id": user['id'],
            "username": user['username']
        })
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "full_name": user['full_name']
            }
        }

@app.get("/api/auth/me")
async def get_current_user(current_user: Dict = Depends(verify_token)):
    """Get current user info"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, full_name, created_at, last_login
            FROM users WHERE id = ?
        ''', (current_user['user_id'],))
        
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return dict(user)

# Protected PDF endpoints
@app.get("/api/pdfs")
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

@app.post("/api/upload")
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
    
    if len(contents) > 50 * 1024 * 1024:
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
                "pdf_id": existing['id']
            }
        
        # Save file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
        stored_filename = f"{current_user['user_id']}_{timestamp}_{safe_filename}"
        file_path = Path("../data/pdf_files") / stored_filename
        
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
            current_user['user_id']
        )
        
        return {
            "success": True,
            "message": "PDF uploaded successfully. Processing in background...",
            "pdf_id": pdf_id,
            "filename": file.filename
        }

@app.post("/api/query")
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

@app.delete("/api/pdfs/{pdf_id}")
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

@app.get("/api/processing-status/{pdf_id}")
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

@app.get("/api/processing-events/{pdf_id}")
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

# Keep existing PDF processing functions
def clean_text(text: str, page_num: int = None) -> str:
    """Clean extracted text from PDF"""
    if not text:
        return ""
    text = ' '.join(text.split())
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('™', "'").replace('œ', '"')
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if page_num == 1:
            cleaned_lines.append(line)
            continue
        
        if line.isdigit() or len(line) < 5 or not any(c.isalnum() for c in line):
            continue
        
        cleaned_lines.append(line)
    
    return ' '.join(cleaned_lines)

def extract_text_from_pdf(pdf_content: bytes) -> List[Dict[str, Any]]:
    """Extract text from PDF"""
    chunks = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                
                cleaned_text = clean_text(text, page_num=page_num)
                if not cleaned_text:
                    continue
                
                text_chunks = split_text_into_chunks(cleaned_text, chunk_size=1000, overlap=200)
                
                for chunk_index, chunk_text in enumerate(text_chunks):
                    if len(chunk_text) > 20:
                        chunks.append({
                            "page": page_num,
                            "chunk": chunk_index,
                            "text": chunk_text
                        })
    
    except Exception as e:
        print(f"Error extracting text: {e}")
        raise
    
    return chunks

def split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks"""
    if not text:
        return []
    
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence_size = len(sentence)
        
        if current_size + sentence_size > chunk_size and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(chunk_text)
            
            overlap_size = 0
            overlap_sentences = []
            for sent in reversed(current_chunk):
                overlap_size += len(sent)
                overlap_sentences.insert(0, sent)
                if overlap_size >= overlap:
                    break
            
            current_chunk = overlap_sentences
            current_size = sum(len(s) for s in current_chunk)
        
        current_chunk.append(sentence)
        current_size += sentence_size
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

async def process_pdf_async(pdf_id: int, pdf_content: bytes, filename: str, user_id: int):
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

if __name__ == "__main__":
    print("\n" + "="*70)
    print("PDF RAG SYSTEM WITH AUTHENTICATION")
    print("="*70)
    print("\n📋 SETUP INSTRUCTIONS:")
    print("1. Install requirements:")
    print("   pip install fastapi uvicorn pdfplumber")
    print("   pip install langchain-ollama langchain-chroma")
    print("   pip install pyjwt bcrypt python-multipart")
    print("\n2. Ensure Ollama is running with required models")
    print("\n3. IMPORTANT: Change SECRET_KEY in production!")
    print("\n🌐 SERVER:")
    print("Starting at: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)