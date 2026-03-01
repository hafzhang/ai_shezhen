#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Initialize SQLite database for development"""

import os
import sys
from pathlib import Path

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Set SQLite database URL before importing any database modules
os.environ['DATABASE_URL'] = 'sqlite:///./shezhen.db'

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api_service.app.core.database import init_db
from sqlalchemy import text

def main():
    print("Initializing SQLite database...")

    try:
        # Initialize database (create tables)
        init_db()
        print("OK Database initialized successfully!")

        # Verify tables were created
        from api_service.app.core.database import engine
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            print(f"OK Created tables: {', '.join(tables)}")

        print("\nDatabase is ready at: sqlite:///./shezhen.db")
        print("You can now start the API server.")

    except Exception as e:
        print(f"ERROR Failed to initialize database: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
