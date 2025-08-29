# auth/routes.py
from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime
from typing import Dict
from models import UserSignup, UserLogin, Token
from database import get_db
from auth.utils import hash_password, verify_password, create_access_token, verify_token

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/signup", response_model=Token)
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

@router.post("/login", response_model=Token)
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

@router.get("/me")
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