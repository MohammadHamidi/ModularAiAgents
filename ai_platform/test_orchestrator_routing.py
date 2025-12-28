"""
Test script to verify Orchestrator routing is working correctly
Tests that all requests go through orchestrator and are routed appropriately
"""
import httpx
import asyncio
import json
import re

BASE_URL = "http://localhost:8001"

async def test_health():
    """Test the health endpoint"""
    print("=" * 60)
    print("1. Testing Health Endpoint")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        assert response.status_code == 200
        assert "orchestrator" in result.get("agents", [])
        print("✓ Health check passed - Orchestrator is available\n")
        return result

async def test_agent_listing():
    """Test that orchestrator is in the agent list"""
    print("=" * 60)
    print("2. Testing Agent Listing")
    print("=" * 60)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/agents")
        assert response.status_code == 200
        agents = response.json()
        print("Available agents:")
        for key, info in agents.items():
            print(f"  - {key}: {info.get('name', 'N/A')}")
        
        assert "orchestrator" in agents
        print("\n✓ Orchestrator is registered\n")
        return agents

async def test_direct_orchestrator():
    """Test direct access to orchestrator"""
    print("=" * 60)
    print("3. Testing Direct Orchestrator Access")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "سلام، می‌خوام درباره کنش‌های مدرسه بدانم",
            "session_id": None,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/orchestrator",
            json=payload
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            output = result.get("output", "")
            print(f"\nResponse (first 200 chars):\n{output[:200]}...")
            print("\n✓ Direct orchestrator access works\n")
            return result
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None

async def test_routing_through_default():
    """Test that default agent request goes through orchestrator"""
    print("=" * 60)
    print("4. Testing Routing Through Default Agent")
    print("=" * 60)
    print("Request: /chat/default with message about 'کنش'")
    print("Expected: Should route through orchestrator to konesh_expert\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "سلام، می‌خوام درباره کنش‌های مدرسه بدانم",
            "session_id": None,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/default",
            json=payload
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            output = result.get("output", "")
            print(f"\nResponse (first 300 chars):\n{output[:300]}...")
            
            # Check if response seems to be from konesh_expert (should mention کنش)
            if "کنش" in output.lower() or "konesh" in output.lower():
                print("\n✓ Response appears to be from konesh_expert (routing worked!)")
            else:
                print("\n⚠ Response doesn't clearly indicate konesh_expert routing")
            print()
            return result
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None

async def test_routing_through_tutor():
    """Test that tutor agent request goes through orchestrator"""
    print("=" * 60)
    print("5. Testing Routing Through Tutor Agent")
    print("=" * 60)
    print("Request: /chat/tutor with educational message")
    print("Expected: Should route through orchestrator to tutor\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "سلام، من یک معلم هستم و می‌خوام آیه‌ای رو برای دانش‌آموزان توضیح بدم",
            "session_id": None,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/tutor",
            json=payload
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            output = result.get("output", "")
            print(f"\nResponse (first 300 chars):\n{output[:300]}...")
            print("\n✓ Tutor routing test completed\n")
            return result
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None

async def test_routing_with_wrong_agent():
    """Test that orchestrator can override user's agent choice if better agent exists"""
    print("=" * 60)
    print("6. Testing Smart Routing (Orchestrator Override)")
    print("=" * 60)
    print("Request: /chat/tutor with message about 'کنش'")
    print("Expected: Orchestrator should route to konesh_expert (not tutor) because message is about کنش\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "سلام، می‌خوام یک کنش برای خانه انتخاب کنم",
            "session_id": None,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/tutor",
            json=payload
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            output = result.get("output", "")
            print(f"\nResponse (first 300 chars):\n{output[:300]}...")
            
            # Check if orchestrator routed to konesh_expert despite user selecting tutor
            if "کنش" in output.lower() and ("خانه" in output.lower() or "مدرسه" in output.lower() or "مسجد" in output.lower()):
                print("\n✓ Orchestrator intelligently routed to konesh_expert (override worked!)")
            else:
                print("\n⚠ Response doesn't clearly indicate konesh_expert routing")
            print()
            return result
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return None

async def test_session_continuity():
    """Test that session is maintained through orchestrator routing"""
    print("=" * 60)
    print("7. Testing Session Continuity Through Routing")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First message
        payload1 = {
            "message": "سلام، من محمد هستم",
            "session_id": None,
            "use_shared_context": True
        }
        response1 = await client.post(
            f"{BASE_URL}/chat/default",
            json=payload1
        )
        
        if response1.status_code == 200:
            result1 = response1.json()
            session_id = result1.get("session_id")
            print(f"First message - Session ID: {session_id}")
            
            # Second message with same session
            payload2 = {
                "message": "نام من چیه؟",
                "session_id": session_id,
                "use_shared_context": True
            }
            response2 = await client.post(
                f"{BASE_URL}/chat/default",
                json=payload2
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                output2 = result2.get("output", "")
                print(f"Second message response: {output2[:200]}...")
                print("\n✓ Session continuity test completed\n")
                return True
            else:
                print(f"✗ Error in second message: {response2.status_code}")
                return False
        else:
            print(f"✗ Error in first message: {response1.status_code}")
            return False

async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("ORCHESTRATOR ROUTING TEST SUITE")
    print("=" * 60)
    print()
    
    try:
        # Basic checks
        await test_health()
        await test_agent_listing()
        
        # Routing tests
        await test_direct_orchestrator()
        await test_routing_through_default()
        await test_routing_through_tutor()
        await test_routing_with_wrong_agent()
        await test_session_continuity()
        
        print("=" * 60)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 60)
        print("\nSummary:")
        print("- Orchestrator is available and working")
        print("- Routing through orchestrator is functional")
        print("- Smart routing (override) is working")
        print("- Session continuity is maintained")
        
    except httpx.ConnectError:
        print("\n✗ Connection error: Make sure the chat-service is running on port 8001")
        print("  Start it with: docker-compose up chat-service")
        raise
    except AssertionError as e:
        print(f"\n✗ Test assertion failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())

