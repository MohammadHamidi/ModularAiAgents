"""
Detailed test to check if history is being loaded and used
"""
import asyncio
import httpx
import json
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"

async def test_detailed():
    """Test with detailed logging"""
    print("=" * 70)
    print("Detailed Session Memory Test")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        session_id = None
        
        # Test 1: First message
        print("\n[TEST 1] First message...")
        msg1 = "سفیران آیه‌ها چیست؟"
        print(f"Message: {msg1}")
        
        r1 = await client.post(
            f"{BASE_URL}/chat/orchestrator",
            json={"message": msg1, "session_id": None, "use_shared_context": True, "user_data": {}}
        )
        
        if r1.status_code != 200:
            print(f"Failed: {r1.status_code}")
            return
        
        d1 = r1.json()
        session_id = d1.get("session_id")
        print(f"Session ID: {session_id}")
        print(f"Response length: {len(d1.get('output', ''))}")
        
        await asyncio.sleep(3)
        
        # Test 2: Check what's in database before second request
        print("\n[CHECK] Verifying session in database...")
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        db_url = os.getenv("DATABASE_URL")
        engine = create_async_engine(db_url)
        
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT jsonb_array_length(messages) as msg_count FROM chat_sessions WHERE session_id = :sid"),
                {"sid": session_id}
            )
            row = result.fetchone()
            if row:
                print(f"Database has {row[0]} messages for this session")
            else:
                print("WARNING: Session not found in database!")
        
        await engine.dispose()
        await asyncio.sleep(2)
        
        # Test 2: Second message
        print("\n[TEST 2] Second message (should remember first)...")
        msg2 = "سوال قبلی من چه بود؟"
        print(f"Message: {msg2}")
        print(f"Using session_id: {session_id}")
        
        r2 = await client.post(
            f"{BASE_URL}/chat/orchestrator",
            json={"message": msg2, "session_id": session_id, "use_shared_context": True, "user_data": {}}
        )
        
        if r2.status_code != 200:
            print(f"Failed: {r2.status_code}")
            return
        
        d2 = r2.json()
        response2 = d2.get("output", "")
        print(f"\nResponse:\n{response2}")
        
        # Check database after second request
        print("\n[CHECK] Verifying session after second request...")
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT jsonb_array_length(messages) as msg_count FROM chat_sessions WHERE session_id = :sid"),
                {"sid": session_id}
            )
            row = result.fetchone()
            if row:
                print(f"Database now has {row[0]} messages for this session")
            else:
                print("WARNING: Session not found in database!")
        
        await engine.dispose()
        
        # Analyze response
        print("\n" + "=" * 70)
        if "سفیران آیه‌ها" in response2 or "سوال قبلی" in response2:
            print("[SUCCESS] Agent appears to remember!")
        elif "نمی‌توانم" in response2 or "دسترسی ندارم" in response2:
            print("[FAILED] Agent says it doesn't remember")
        else:
            print("[UNCLEAR] Response unclear")

if __name__ == "__main__":
    asyncio.run(test_detailed())

