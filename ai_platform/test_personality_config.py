"""
Test script to verify personality configurations are loaded correctly
and agents follow the new comprehensive instructions (هسته سخت منطقی)
"""
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8001"

async def test_default_agent_identity():
    """Test that default agent has correct identity"""
    print("=" * 60)
    print("Testing Default Agent Identity and Core Logic")
    print("=" * 60)
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test with a question about an Ayah (verse)
        payload = {
            "message": "سلام، می‌خوام درباره آیه «وَمَا خَلَقْتُ الْجِنَّ وَالْإِنسَ إِلَّا لِيَعْبُدُونِ» بیشتر بدانم و یک کنش ساده برای اجرا پیشنهاد بده",
            "session_id": None,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/default",
            json=payload
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        output = result.get("output", "")
        
        print("\n" + "=" * 60)
        print("Agent Response:")
        print("=" * 60)
        print(output)
        print("=" * 60)
        
        # Check for core logic components (هسته سخت منطقی)
        checks = {
            "تبیین (فهم امروزی)": any(keyword in output.lower() for keyword in [
                "میگه", "معنی", "فهم", "توضیح", "مفهوم", "یعنی"
            ]),
            "اتصال به عمل": any(keyword in output.lower() for keyword in [
                "کنش", "اقدام", "انجام", "عمل", "پیشنهاد", "بکن", "انجام بده"
            ]),
            "تلاوت": any(keyword in output.lower() for keyword in [
                "آیه", "تلاوت", "بخوان", "قرآن"
            ]),
            "پیشنهادهای بعدی": "پیشنهاد" in output or "بعدی" in output
        }
        
        print("\n" + "=" * 60)
        print("Core Logic Verification (هسته سخت منطقی):")
        print("=" * 60)
        all_passed = True
        for component, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"{status} {component}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        print("=" * 60)
        if all_passed:
            print("✓ All core logic components found!")
        else:
            print("⚠ Some core logic components missing")
        print("=" * 60)
        
        return all_passed

async def test_friendly_tutor_agent():
    """Test friendly tutor agent"""
    print("\n" + "=" * 60)
    print("Testing Friendly Tutor Agent (tutor)")
    print("=" * 60)
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "سلام، من یک معلم هستم و می‌خوام آیه‌ای رو برای دانش‌آموزان کلاسم توضیح بدم. کمکم کن",
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
            print("\nResponse:")
            print(output)
            print("\n✓ Friendly tutor agent responded")
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)

async def test_konesh_expert_agent():
    """Test konesh expert agent"""
    print("\n" + "=" * 60)
    print("Testing Konesh Expert Agent")
    print("=" * 60)
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "message": "سلام، می‌خوام یک کنش برای خانه انتخاب کنم. کمکم کن",
            "session_id": None,
            "use_shared_context": True
        }
        response = await client.post(
            f"{BASE_URL}/chat/konesh_expert",
            json=payload
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            output = result.get("output", "")
            print("\nResponse:")
            print(output)
            print("\n✓ Konesh expert agent responded")
        else:
            print(f"✗ Error: {response.status_code}")
            print(response.text)

async def test_agent_listing():
    """Test that all personality agents are listed"""
    print("\n" + "=" * 60)
    print("Testing Agent Listing")
    print("=" * 60)
    print()
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/agents")
        if response.status_code == 200:
            agents = response.json()
            print("Available agents:")
            for agent_key, agent_info in agents.items():
                print(f"  - {agent_key}: {agent_info.get('name', 'N/A')}")
            print("\n✓ Agent listing successful")
        else:
            print(f"✗ Error: {response.status_code}")

async def main():
    """Run all personality tests"""
    try:
        await test_agent_listing()
        await test_default_agent_identity()
        await test_friendly_tutor_agent()
        await test_konesh_expert_agent()
        
        print("\n" + "=" * 60)
        print("Personality Configuration Tests Completed!")
        print("=" * 60)
    except httpx.ConnectError:
        print("\n✗ Connection error: Make sure the chat-service is running on port 8001")
        raise
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())

