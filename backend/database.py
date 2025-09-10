# database.py
import sqlite3
from datetime import datetime
import bcrypt

# Database configuration
DB_PATH = "rag_system.db"

def init_database():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table with role field
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'student',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # PDFs table with visibility field
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            page_count INTEGER,
            processing_status TEXT DEFAULT 'pending',
            visibility TEXT DEFAULT 'private',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # PDF chunks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdf_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            page_number INTEGER,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE
        )
    ''')
    
    # Query logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            sources TEXT,
            response_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Handle database migration - add missing columns if they don't exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'role' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "student"')
        conn.commit()
    
    cursor.execute("PRAGMA table_info(pdfs)")
    pdf_columns = [column[1] for column in cursor.fetchall()]
    
    if 'visibility' not in pdf_columns:
        cursor.execute('ALTER TABLE pdfs ADD COLUMN visibility TEXT DEFAULT "private"')
        conn.commit()
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pdfs_user_id ON pdfs(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pdfs_visibility ON pdfs(visibility)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pdf_chunks_pdf_id ON pdf_chunks(pdf_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_query_logs_user_id ON query_logs(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
    
    # Create default admin user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        admin_password = "admin123"  # Change this in production!
        password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin@utar.edu.my', password_hash, 'System Administrator', 'admin'))
        
        print("\n⚠️  DEFAULT ADMIN ACCOUNT CREATED:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   PLEASE CHANGE THIS PASSWORD IMMEDIATELY!\n")
    
    conn.commit()
    conn.close()
    
    print("✅ Database initialized successfully")

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn