"""
Script to initialize the database schema.
Creates the required tables for session memory and context management.
"""
import asyncio
import sys
import io
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

async def setup_database():
    """Create database tables if they don't exist"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        print("Please set DATABASE_URL in .env file")
        return False
    
    print("=" * 70)
    print("Database Schema Setup")
    print("=" * 70)
    print(f"Connecting to database...")
    print(f"URL: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    
    try:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        
        # Read init.sql
        init_sql_path = os.path.join(os.path.dirname(__file__), "db", "init.sql")
        if not os.path.exists(init_sql_path):
            print(f"ERROR: init.sql not found at {init_sql_path}")
            return False
        
        with open(init_sql_path, 'r', encoding='utf-8') as f:
            init_sql = f.read()
        
        print("\nCreating tables...")
        async with engine.begin() as conn:
            # Split SQL into individual statements and execute them one by one
            # asyncpg doesn't support multiple statements in one execute()
            # Remove comments and split by semicolon
            lines = init_sql.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('--'):
                    cleaned_lines.append(line)
            
            # Join and split by semicolon
            full_sql = ' '.join(cleaned_lines)
            statements = [s.strip() + ';' for s in full_sql.split(';') if s.strip()]
            
            for i, statement in enumerate(statements, 1):
                if statement and statement != ';':
                    try:
                        await conn.execute(text(statement))
                        # Extract what we're creating for better logging
                        if 'CREATE TABLE' in statement.upper():
                            table_name = statement.split('(')[0].split()[-1] if '(' in statement else 'table'
                            print(f"  [{i}/{len(statements)}] Created table: {table_name}")
                        elif 'CREATE INDEX' in statement.upper():
                            index_name = statement.split('ON')[0].split()[-1] if 'ON' in statement else 'index'
                            print(f"  [{i}/{len(statements)}] Created index: {index_name}")
                        else:
                            print(f"  [{i}/{len(statements)}] Executed statement")
                    except Exception as e:
                        error_msg = str(e).lower()
                        # Some statements might fail if tables/indexes already exist, which is OK
                        if "already exists" in error_msg or "duplicate" in error_msg:
                            print(f"  [{i}/{len(statements)}] Skipped (already exists)")
                        elif "does not exist" in error_msg and "index" in statement.lower():
                            # Index creation failed because table doesn't exist yet - this shouldn't happen with proper ordering
                            print(f"  [{i}/{len(statements)}] Warning: {error_msg[:50]}")
                            # Don't raise, continue
                        else:
                            print(f"  [{i}/{len(statements)}] Error: {error_msg[:100]}")
                            raise
        
        print("[SUCCESS] Database schema created successfully!")
        
        # Verify tables exist
        print("\nVerifying tables...")
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('chat_sessions', 'agent_context')
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            
            if 'chat_sessions' in tables and 'agent_context' in tables:
                print("[SUCCESS] Both required tables exist:")
                print(f"   - chat_sessions")
                print(f"   - agent_context")
                return True
            else:
                print("[WARNING] Some tables are missing:")
                print(f"   - chat_sessions: {'[OK]' if 'chat_sessions' in tables else '[MISSING]'}")
                print(f"   - agent_context: {'[OK]' if 'agent_context' in tables else '[MISSING]'}")
                return False
        
    except Exception as e:
        print(f"[ERROR] Error setting up database: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            await engine.dispose()
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(setup_database())
    sys.exit(0 if success else 1)

