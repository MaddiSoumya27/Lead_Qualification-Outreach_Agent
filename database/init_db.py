"""
Database initialization script for LQOA
Creates tables and seeds default users for initial setup
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import create_tables, get_database_session
from database.repositories import UserRepository
from database.models import User

def init_database():
    """Initialize database with tables and default users"""
    print("Initializing LQOA database...")
    
    # Create tables
    print("Creating database tables...")
    create_tables()
    print("✓ Database tables created")
    
    # Create default users
    print("Creating default users...")
    with get_database_session() as session:
        user_repo = UserRepository(session)
        
        # Check if users already exist
        existing_admin = user_repo.get_by_username("admin")
        if existing_admin:
            print("✓ Default users already exist, skipping creation")
            return
        
        # Create default users
        default_users = [
            {
                "username": "admin",
                "password": "admin123",
                "email": "admin@lqoa.local",
                "role": "admin"
            },
            {
                "username": "reviewer",
                "password": "review123",
                "email": "reviewer@lqoa.local",
                "role": "reviewer"
            },
            {
                "username": "viewer",
                "password": "view123",
                "email": "viewer@lqoa.local",
                "role": "viewer"
            }
        ]
        
        for user_data in default_users:
            try:
                user = user_repo.create_user(
                    username=user_data["username"],
                    password=user_data["password"],
                    email=user_data["email"],
                    role=user_data["role"]
                )
                print(f"✓ Created user: {user.username} ({user.role})")
            except Exception as e:
                print(f"✗ Failed to create user {user_data['username']}: {str(e)}")
    
    print("✓ Database initialization complete!")
    print()
    print("Default user accounts:")
    print("  Admin:    username=admin,    password=admin123")
    print("  Reviewer: username=reviewer, password=review123")
    print("  Viewer:   username=viewer,   password=view123")
    print()
    print("⚠️  IMPORTANT: Change these passwords in production!")

def reset_database():
    """Reset database - use with caution!"""
    from database.connection import drop_tables
    
    print("⚠️  WARNING: This will delete all data!")
    confirmation = input("Type 'RESET' to confirm: ")
    
    if confirmation == "RESET":
        print("Dropping all tables...")
        drop_tables()
        print("✓ All tables dropped")
        
        print("Reinitializing database...")
        init_database()
        print("✓ Database reset complete")
    else:
        print("Database reset cancelled")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LQOA Database Management")
    parser.add_argument("--reset", action="store_true", help="Reset database (destructive)")
    args = parser.parse_args()
    
    if args.reset:
        reset_database()
    else:
        init_database()