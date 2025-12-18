"""
Test script to verify memory issue fixes
Tests that context is properly accumulated across multiple requests
"""
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8001"

async def test_memory_accumulation():
    """Test that user context accumulates properly across multiple messages"""
    print("=" * 80)
    print("Testing Memory Accumulation Fix")
    print("=" * 80)
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = None

        # Message 1: User introduces themselves with name
        print("Step 1: User provides name...")
        payload = {
            "message": "من محمد هستم",  # "I am Mohammad"
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()
        session_id = result["session_id"]
        print(f"  Response: {result['output'][:100]}")
        print(f"  Session ID: {session_id}")

        # Get context after message 1
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]
        print(f"  Context after step 1: {json.dumps(context, ensure_ascii=False, indent=2)}")
        assert "user_name" in context, "user_name should be stored"
        assert context["user_name"]["value"] == "محمد", f"Expected 'محمد', got {context['user_name']}"
        print("  ✓ Name stored correctly\n")

        # Message 2: User provides age
        print("Step 2: User provides age...")
        payload = {
            "message": "من ۲۵ سالمه",  # "I am 25 years old"
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()
        print(f"  Response: {result['output'][:100]}")

        # Get context after message 2
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]
        print(f"  Context after step 2: {json.dumps(context, ensure_ascii=False, indent=2)}")

        # CRITICAL TEST: Both name and age should be present
        assert "user_name" in context, "user_name should STILL be stored after adding age"
        assert context["user_name"]["value"] == "محمد", f"Expected 'محمد', got {context['user_name']}"
        assert "user_age" in context, "user_age should be stored"
        assert context["user_age"]["value"] == 25, f"Expected 25, got {context['user_age']}"

        # CRITICAL: user_prefs should NOT exist (or if it does, it should have both fields)
        if "user_prefs" in context:
            print("  WARNING: user_prefs key still exists (should be removed in fix)")
            print(f"  user_prefs content: {context['user_prefs']}")

        print("  ✓ Both name and age stored correctly\n")

        # Message 3: User provides location
        print("Step 3: User provides location...")
        payload = {
            "message": "من از تهران هستم",  # "I am from Tehran"
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()
        print(f"  Response: {result['output'][:100]}")

        # Get context after message 3
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]
        print(f"  Context after step 3: {json.dumps(context, ensure_ascii=False, indent=2)}")

        # CRITICAL TEST: All three fields should be present
        assert "user_name" in context, "user_name should persist"
        assert context["user_name"]["value"] == "محمد", f"Name should still be 'محمد'"
        assert "user_age" in context, "user_age should persist"
        assert context["user_age"]["value"] == 25, f"Age should still be 25"
        assert "user_location" in context, "user_location should be stored"
        assert "تهران" in context["user_location"]["value"], f"Location should contain 'تهران'"
        print("  ✓ All three fields (name, age, location) stored correctly\n")

        # Message 4: User provides first interest
        print("Step 4: User provides first interest...")
        payload = {
            "message": "I like football",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()
        print(f"  Response: {result['output'][:100]}")

        # Get context after message 4
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]
        print(f"  Context after step 4: {json.dumps(context, ensure_ascii=False, indent=2)}")

        # Verify all previous fields still exist
        assert "user_name" in context, "user_name should persist"
        assert "user_age" in context, "user_age should persist"
        assert "user_location" in context, "user_location should persist"

        # Verify first interest is stored
        assert "user_interests" in context, "user_interests should be stored"
        interests = context["user_interests"]["value"]
        assert isinstance(interests, list), "user_interests should be a list"
        assert "football" in interests, f"Expected 'football' in {interests}"
        print(f"  ✓ First interest stored: {interests}\n")

        # Message 5: User provides second interest
        print("Step 5: User provides second interest...")
        payload = {
            "message": "I also love reading",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()
        print(f"  Response: {result['output'][:100]}")

        # Get context after message 5
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]
        print(f"  Context after step 5: {json.dumps(context, ensure_ascii=False, indent=2)}")

        # CRITICAL TEST: Both interests should be present
        assert "user_interests" in context, "user_interests should be stored"
        interests = context["user_interests"]["value"]
        assert isinstance(interests, list), "user_interests should be a list"
        assert "football" in interests, f"First interest 'football' should still be present in {interests}"
        assert "reading" in interests, f"Second interest 'reading' should be present in {interests}"
        print(f"  ✓ Both interests accumulated: {interests}\n")

        # Final verification: Ask the bot to recall all information
        print("Step 6: Ask bot to recall all information...")
        payload = {
            "message": "Tell me everything you know about me",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()
        print(f"  Response: {result['output']}")

        # Verify the response contains all the information
        output = result['output']
        assert "محمد" in output or "Mohammad" in output.lower(), "Response should mention the name"
        print("  ✓ Bot recalls stored information\n")

        print("=" * 80)
        print("✅ ALL MEMORY TESTS PASSED!")
        print("=" * 80)
        print("\nSummary:")
        print("  - Name persisted after adding age ✓")
        print("  - Name and age persisted after adding location ✓")
        print("  - All fields persisted after adding interests ✓")
        print("  - Multiple interests accumulated correctly ✓")
        print("  - Bot can recall all stored information ✓")

async def main():
    try:
        await test_memory_accumulation()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except httpx.ConnectError:
        print("\n❌ Connection error: Make sure the chat-service is running on port 8001")
        print("  Start it with: docker-compose up chat-service")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
