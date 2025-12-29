"""
Simplified test script to verify session memory is working correctly.
Uses non-streaming endpoint for easier debugging.
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

BASE_URL = "http://localhost:8000"  # Gateway URL

async def test_session_memory():
    """Test that agents remember previous conversation turns"""
    print("=" * 70)
    print("Session Memory Test (Non-Streaming)")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test gateway health
        try:
            health = await client.get(f"{BASE_URL}/health")
            print(f"Gateway health: {health.status_code}")
        except Exception as e:
            print(f"ERROR: Cannot connect to gateway: {e}")
            return
        
        session_id = None
        
        # Test 1: Send first message
        first_message = "سفیران آیه‌ها چیست؟"
        print("\n[TEST 1] Sending first message...")
        print(f"Message: {first_message}")
        
        response1 = await client.post(
            f"{BASE_URL}/chat/orchestrator",
            json={
                "message": first_message,
                "session_id": session_id,
                "use_shared_context": True,
                "user_data": {}
            }
        )
        
        if response1.status_code != 200:
            print(f"❌ Failed: {response1.status_code}")
            print(f"Response: {response1.text}")
            return
        
        data1 = response1.json()
        session_id = data1.get("session_id")
        response1_text = data1.get("output", "")
        
        print(f"✅ Response received ({len(response1_text)} chars)")
        print(f"✅ Session ID: {session_id}")
        print(f"Response preview: {response1_text[:150]}...")
        
        if not session_id:
            print("❌ No session_id received!")
            return
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Test 2: Send follow-up message asking about previous question
        second_message = "سوال قبلی من چه بود؟"
        print("\n[TEST 2] Sending follow-up message...")
        print(f"Message: {second_message} (What was my previous question?)")
        print(f"Using session_id: {session_id}")
        
        response2 = await client.post(
            f"{BASE_URL}/chat/orchestrator",
            json={
                "message": second_message,
                "session_id": session_id,  # Use same session_id
                "use_shared_context": True,
                "user_data": {}
            }
        )
        
        if response2.status_code != 200:
            print(f"❌ Failed: {response2.status_code}")
            print(f"Response: {response2.text}")
            return
        
        data2 = response2.json()
        response2_text = data2.get("output", "")
        session_id2 = data2.get("session_id")
        
        print(f"✅ Response received ({len(response2_text)} chars)")
        if session_id2 and session_id2 != session_id:
            print(f"⚠️  Session ID changed: {session_id} -> {session_id2}")
        print(f"\nFull response:\n{response2_text}")
        
        # Check if agent remembered the previous question
        print("\n" + "=" * 70)
        print("Memory Test Results")
        print("=" * 70)
        
        # Check for indicators that agent remembered
        remembered_indicators = [
            "سفیران آیه‌ها",
            "سوال قبلی",
            "پرسیدید",
            "گفتید",
            "سوال شما",
            "سوال قبل",
            "پرسیدم"
        ]
        
        # Also check for negative indicators (agent saying it doesn't remember)
        no_memory_indicators = [
            "نمی‌توانم",
            "یادم نیست",
            "حافظه",
            "دسترسی ندارم",
            "به یاد نمی‌آورم",
            "نمیتوانم",
            "یاد ندارم"
        ]
        
        has_memory = any(indicator in response2_text for indicator in remembered_indicators)
        has_no_memory = any(indicator in response2_text for indicator in no_memory_indicators)
        
        print(f"\nMemory indicators found: {has_memory}")
        print(f"No-memory indicators found: {has_no_memory}")
        
        if has_memory and not has_no_memory:
            print("\n✅ SUCCESS: Agent remembered the previous question!")
            print("✅ Session memory is working correctly!")
            result = "SUCCESS"
        elif has_no_memory:
            print("\n❌ FAILED: Agent says it doesn't remember")
            print("❌ Session memory is NOT working")
            result = "FAILED"
        else:
            print("\n⚠️  UNCLEAR: Response doesn't clearly indicate memory status")
            print("   Check the response above to verify")
            result = "UNCLEAR"
        
        # Test 3: Check session context via API
        print("\n[TEST 3] Checking session context via API...")
        try:
            context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
            
            if context_response.status_code == 200:
                context_data = context_response.json()
                print(f"✅ Session context retrieved")
                context = context_data.get("context", {})
                print(f"   Context keys: {list(context.keys())}")
                if context:
                    print(f"   Context has data: Yes")
                else:
                    print(f"   Context has data: No (empty)")
            else:
                print(f"⚠️  Could not retrieve context: {context_response.status_code}")
        except Exception as e:
            print(f"⚠️  Error retrieving context: {e}")
        
        print("\n" + "=" * 70)
        print("Test Complete")
        print("=" * 70)
        print(f"Session ID: {session_id}")
        print(f"Result: {result}")
        print(f"\nUse this session_id to continue the conversation: {session_id}")

if __name__ == "__main__":
    asyncio.run(test_session_memory())

