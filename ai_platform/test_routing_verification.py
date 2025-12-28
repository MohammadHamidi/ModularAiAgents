"""
Quick test to verify routing is working
"""
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8001"

async def test_routing_flow():
    """Test the routing flow"""
    print("Testing Routing Flow")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Request with message that should route to konesh_expert
        print("\nTest 1: Request about 'کنش' through /chat/default")
        print("Expected: Should go through orchestrator → konesh_expert")
        
        payload = {
            "message": "سلام، می‌خوام یک کنش برای خانه انتخاب کنم",
            "session_id": None,
            "use_shared_context": True
        }
        
        response = await client.post(
            f"{BASE_URL}/chat/default",
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            output = result.get("output", "")
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response Length: {len(output)} chars")
            print(f"\nFirst 400 chars of response:")
            print("-" * 60)
            print(output[:400])
            print("-" * 60)
            
            # Check indicators
            has_konesh_keywords = any(kw in output.lower() for kw in ["کنش", "خانه", "مدرسه", "مسجد"])
            has_routing_indicators = "کنش" in output.lower()
            
            print(f"\nAnalysis:")
            print(f"  - Contains 'کنش' keywords: {has_konesh_keywords}")
            print(f"  - Appears to be about actions: {has_routing_indicators}")
            
            if has_konesh_keywords:
                print("\n✅ Routing appears to be working - response mentions 'کنش'")
            else:
                print("\n⚠️  Response doesn't clearly indicate konesh_expert routing")
                print("   (This might be because konesh_expert agent is not loaded yet)")
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_routing_flow())

