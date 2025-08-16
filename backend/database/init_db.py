#!/usr/bin/env python3
"""
Database initialization script for Codebase Time Machine
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from models import init_database, get_database_url
from dotenv import load_dotenv

def main():
    """Initialize the database."""
    # Load environment variables
    load_dotenv()
    
    print("Initializing Codebase Time Machine database...")
    
    # Get database path
    db_url = get_database_url()
    db_path = db_url.replace('sqlite:///', '')
    
    print(f"Database location: {db_path}")
    
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        print(f"Created directory: {db_dir}")
    
    # Initialize database
    try:
        init_database()
        print("✅ Database initialized successfully!")
        print("\nTables created:")
        print("  - repositories")
        print("  - commits")
        print("  - files")
        print("  - file_changes")
        print("  - ownership")
        print("  - patterns")
        print("  - complexity_history")
        print("  - query_cache")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()