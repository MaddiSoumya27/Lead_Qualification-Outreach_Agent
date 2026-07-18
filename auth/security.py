"""
Authentication and security utilities for LQOA
"""

import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from passlib.hash import bcrypt

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-this-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def generate_secure_key() -> str:
    """Generate a secure random key for JWT signing"""
    import secrets
    return secrets.token_urlsafe(32)

# Role-based permissions
ROLE_PERMISSIONS = {
    "admin": [
        "create_user",
        "delete_user",
        "modify_user",
        "view_all_leads",
        "approve_leads",
        "reject_leads",
        "view_analytics",
        "view_governance",
        "export_data"
    ],
    "reviewer": [
        "view_all_leads",
        "approve_leads",
        "reject_leads",
        "view_governance"
    ],
    "viewer": [
        "view_own_leads",
        "submit_leads"
    ]
}

def check_permission(user_role: str, permission: str) -> bool:
    """Check if a user role has a specific permission"""
    return permission in ROLE_PERMISSIONS.get(user_role, [])

def get_user_permissions(user_role: str) -> list:
    """Get all permissions for a user role"""
    return ROLE_PERMISSIONS.get(user_role, [])