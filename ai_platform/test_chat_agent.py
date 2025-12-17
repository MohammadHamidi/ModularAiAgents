"""
Test script for chat_agent service
Tests the health endpoint, agent listing, and chat functionality
"""
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8001"

async def test_health():
    """Test the health endpoint"""
    print("Testing /health endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    print("✓ Health check passed\n")

async def test_list_agents():
    """Test listing available agents"""
    print("Testing /agents endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/agents")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 200
        agents = response.json()
        assert "default" in agents
        assert "translator" in agents
    print("✓ Agent listing passed\n")

async def test_chat_default_agent():
    """Test chat with default agent"""
    print("Testing /chat/default endpoint...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "Hello, how are you?",
            "session_id": None,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/default",
            json=payload
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        assert response.status_code == 200
        assert "session_id" in result
        assert "output" in result
        assert len(result["session_id"]) > 0
        print(f"✓ Default chat test passed (session_id: {result['session_id']})\n")
        return result["session_id"]

async def test_chat_with_session(session_id: str):
    """Test chat with existing session"""
    print(f"Testing /chat/default with session_id: {session_id}...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "What was my previous message?",
            "session_id": session_id,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/default",
            json=payload
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        assert response.status_code == 200
        assert result["session_id"] == session_id
        assert "output" in result
    print("✓ Session continuity test passed\n")

async def test_translator_agent():
    """Test translator agent"""
    print("Testing /chat/translator endpoint...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "Hello world",
            "session_id": None,
            "use_shared_context": False
        }
        response = await client.post(
            f"{BASE_URL}/chat/translator",
            json=payload
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        assert response.status_code == 200
        assert "output" in result
    print("✓ Translator agent test passed\n")

async def test_session_context(session_id: str):
    """Test getting session context"""
    print(f"Testing /session/{session_id}/context endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/session/{session_id}/context")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        assert response.status_code == 200
        assert "context" in result
    print("✓ Session context test passed\n")

async def main():
    """Run all tests"""
    print("=" * 60)
    print("Starting Chat Agent Service Tests")
    print("=" * 60)
    print()
    
    try:
        await test_health()
        await test_list_agents()
        session_id = await test_chat_default_agent()
        await test_chat_with_session(session_id)
        await test_translator_agent()
        await test_session_context(session_id)
        
        print("=" * 60)
        print("All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        raise
    except httpx.ConnectError:
        print("\n✗ Connection error: Make sure the chat-service is running on port 8001")
        print("  Start it with: docker-compose up chat-service")
        raise
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

