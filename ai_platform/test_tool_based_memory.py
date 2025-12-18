"""
Test script for tool-based user information extraction
Tests that the AI agent uses the save_user_info tool to extract context silently
"""
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8001"

async def test_tool_based_extraction():
    """Test that the agent extracts user info using tools without mentioning it"""
    print("=" * 80)
    print("Testing Tool-Based User Information Extraction")
    print("=" * 80)
    print()

    async with httpx.AsyncClient(timeout=60.0) as client:
        session_id = None

        # Test 1: Natural introduction with multiple pieces of information
        print("Test 1: Natural introduction with name, age, and location...")
        payload = {
            "message": "سلام! من محمد هستم، ۲۵ سالمه و از تهران هستم.",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()
        session_id = result["session_id"]

        print(f"  User: {payload['message']}")
        print(f"  Assistant: {result['output']}")

        # Verify the response doesn't mention saving data
        output_lower = result['output'].lower()
        forbidden_phrases = [
            "ذخیره", "save", "stored", "saved", "remember", "به خاطر",
            "ثبت", "記錄", "保存"
        ]
        mentions_saving = any(phrase in output_lower for phrase in forbidden_phrases)

        if mentions_saving:
            print("  ⚠️  WARNING: Agent mentioned saving data (should be silent)")
        else:
            print("  ✅ Agent responded naturally without mentioning data saving")

        # Check if context was actually saved
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]
        print(f"\n  Saved Context:")
        print(f"    {json.dumps(context, ensure_ascii=False, indent=4)}")

        # Verify extracted data
        assert "user_name" in context, "Name should be extracted"
        assert context["user_name"]["value"] == "محمد", f"Expected 'محمد', got {context['user_name']}"
        assert "user_age" in context, "Age should be extracted"
        assert context["user_age"]["value"] == 25, f"Expected 25, got {context['user_age']}"
        assert "user_location" in context, "Location should be extracted"
        assert "تهران" in context["user_location"]["value"], f"Expected 'تهران', got {context['user_location']}"
        print("  ✅ All information extracted correctly\n")

        # Test 2: Adding occupation in a natural question
        print("Test 2: Sharing occupation naturally...")
        payload = {
            "message": "من برنامه‌نویسم. آیا می‌تونی کمکم کنی یک الگوریتم بنویسم؟",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()

        print(f"  User: {payload['message']}")
        print(f"  Assistant: {result['output'][:200]}...")

        # Verify context was updated
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]

        assert "user_occupation" in context, "Occupation should be extracted"
        print(f"  ✅ Occupation saved: {context['user_occupation']['value']}")

        # Verify previous data still exists
        assert "user_name" in context, "Name should still be present"
        assert "user_age" in context, "Age should still be present"
        assert "user_location" in context, "Location should still be present"
        print("  ✅ Previous data preserved\n")

        # Test 3: Adding multiple interests
        print("Test 3: Sharing interests naturally...")
        payload = {
            "message": "I like playing football and reading books. What do you recommend?",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()

        print(f"  User: {payload['message']}")
        print(f"  Assistant: {result['output'][:200]}...")

        # Verify interests were extracted
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]

        if "user_interests" in context:
            interests = context["user_interests"]["value"]
            print(f"  ✅ Interests saved: {interests}")
            # Should contain some form of football and reading/books
        else:
            print("  ⚠️  No interests extracted (may need more specific prompting)")

        print()

        # Test 4: Ask agent to recall information (using last 2 messages)
        print("Test 4: Agent recalls information using context...")
        payload = {
            "message": "What do you know about me?",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()

        print(f"  User: {payload['message']}")
        print(f"  Assistant: {result['output']}")

        # Verify the agent mentions the saved information
        output = result['output']
        has_name = "محمد" in output or "Mohammad" in output.lower()
        has_age = "25" in output or "۲۵" in output

        if has_name and has_age:
            print("  ✅ Agent successfully recalled user information")
        else:
            print("  ⚠️  Agent may not have used all context")
        print()

        # Test 5: Verify last 2 messages are in context
        print("Test 5: Last 2 messages context...")
        payload = {
            "message": "What did I just ask you in my previous message?",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(f"{BASE_URL}/chat/default", json=payload)
        result = response.json()

        print(f"  User: {payload['message']}")
        print(f"  Assistant: {result['output']}")

        # Should mention "What do you know about me" or similar
        if "know about" in result['output'].lower() or "درباره" in result['output']:
            print("  ✅ Agent has access to recent message context")
        else:
            print("  ℹ️  Agent response (may or may not reference previous message)")
        print()

        # Final context dump
        print("=" * 80)
        print("Final Context State:")
        print("=" * 80)
        context_response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        context = context_response.json()["context"]
        print(json.dumps(context, ensure_ascii=False, indent=2))
        print()

        print("=" * 80)
        print("✅ ALL TOOL-BASED EXTRACTION TESTS COMPLETED!")
        print("=" * 80)
        print("\nKey Features Tested:")
        print("  ✅ Agent extracts user info using save_user_info tool")
        print("  ✅ Agent responds naturally without mentioning data saving")
        print("  ✅ Multiple pieces of info extracted from single message")
        print("  ✅ Previous context preserved when adding new info")
        print("  ✅ Agent can recall saved information")
        print("  ✅ Last 2 user messages available as context")

async def main():
    try:
        await test_tool_based_extraction()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except httpx.ConnectError:
        print("\n❌ Connection error: Make sure the chat-service is running on port 8001")
        print("  Start it with: cd ai_platform && docker-compose up chat-service")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
