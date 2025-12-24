#!/usr/bin/env python3
"""
Test script for Orchestrator Agent
Tests automatic routing to specialist agents based on message content
"""
import asyncio
import httpx
import json
from typing import List, Dict
from datetime import datetime


# Test cases covering different specialist agents
TEST_CASES = [
    {
        "message": "سلام، سردرد دارم و تب کردم",
        "expected_agent": "doctor",
        "category": "Medical",
        "language": "Persian"
    },
    {
        "message": "I have a headache and fever",
        "expected_agent": "doctor",
        "category": "Medical",
        "language": "English"
    },
    {
        "message": "می‌خوام ریاضی یاد بگیرم",
        "expected_agent": "tutor",
        "category": "Educational",
        "language": "Persian"
    },
    {
        "message": "Help me with my homework on calculus",
        "expected_agent": "tutor",
        "category": "Educational",
        "language": "English"
    },
    {
        "message": "درباره آیه 12 بگو",
        "expected_agent": "default",
        "category": "Religious",
        "language": "Persian"
    },
    {
        "message": "چطور یک کنش ثبت کنم؟",
        "expected_agent": "default",
        "category": "Religious/Platform",
        "language": "Persian"
    },
    {
        "message": "I need help with a business proposal",
        "expected_agent": "professional",
        "category": "Business",
        "language": "English"
    },
    {
        "message": "می‌خوام درباره شرکت گوگل بدونم",
        "expected_agent": "professional",
        "category": "Business",
        "language": "Persian"
    },
    {
        "message": "I want maximum privacy",
        "expected_agent": "minimal",
        "category": "Privacy",
        "language": "English"
    }
]


class OrchestratorTester:
    """Test harness for Orchestrator Agent"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []

    async def test_single_case(self, test_case: Dict, session_id: str = None) -> Dict:
        """Test a single routing case"""
        print(f"\n{'='*70}")
        print(f"🧪 Test: {test_case['category']} ({test_case['language']})")
        print(f"📨 Message: {test_case['message']}")
        print(f"🎯 Expected Agent: {test_case['expected_agent']}")
        print(f"{'='*70}")

        result = {
            "test_case": test_case,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "response": None,
            "response_length": 0
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/orchestrator",
                    json={
                        "message": test_case["message"],
                        "session_id": session_id
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    result["success"] = True
                    result["response"] = data.get("output", "")
                    result["response_length"] = len(result["response"])
                    result["session_id"] = data.get("session_id")

                    print(f"\n✅ SUCCESS - Response received:")
                    print(f"   📊 Length: {result['response_length']} characters")
                    print(f"   📝 Response preview:")
                    preview = result["response"][:200].replace("\n", " ")
                    print(f"   {preview}...")

                    # Try to infer which agent was used (basic heuristic)
                    response_lower = result["response"].lower()
                    inferred_agent = "unknown"

                    if any(word in response_lower for word in ["دکتر", "پزشک", "سلامت", "بیماری", "medical", "health"]):
                        inferred_agent = "doctor"
                    elif any(word in response_lower for word in ["یادگیری", "درس", "آموزش", "learn", "study", "homework"]):
                        inferred_agent = "tutor"
                    elif any(word in response_lower for word in ["آیه", "قرآن", "کنش", "سفیران", "verse"]):
                        inferred_agent = "default"
                    elif any(word in response_lower for word in ["کسب‌وکار", "شرکت", "business", "company"]):
                        inferred_agent = "professional"

                    result["inferred_agent"] = inferred_agent

                    if inferred_agent == test_case["expected_agent"]:
                        print(f"   ✅ Routing appears correct: {inferred_agent}")
                    else:
                        print(f"   ⚠️  Inferred agent: {inferred_agent} (expected: {test_case['expected_agent']})")

                else:
                    result["error"] = f"HTTP {response.status_code}: {response.text}"
                    print(f"\n❌ FAILED - HTTP {response.status_code}")
                    print(f"   Error: {response.text[:200]}")

        except Exception as e:
            result["error"] = str(e)
            print(f"\n❌ EXCEPTION: {e}")

        self.results.append(result)
        return result

    async def test_all(self, session_id: str = None):
        """Test all cases"""
        print("\n" + "="*70)
        print("🚀 ORCHESTRATOR AGENT TEST SUITE")
        print("="*70)
        print(f"📍 Base URL: {self.base_url}")
        print(f"📊 Total Tests: {len(TEST_CASES)}")
        print(f"🕒 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        for i, test_case in enumerate(TEST_CASES, 1):
            print(f"\n\n[{i}/{len(TEST_CASES)}]")
            await self.test_single_case(test_case, session_id)
            await asyncio.sleep(0.5)  # Small delay between tests

        self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        print("\n\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)

        total = len(self.results)
        successful = sum(1 for r in self.results if r["success"])
        failed = total - successful

        print(f"Total Tests: {total}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(successful/total*100):.1f}%")

        if failed > 0:
            print("\n❌ Failed Tests:")
            for i, result in enumerate(self.results, 1):
                if not result["success"]:
                    tc = result["test_case"]
                    print(f"   {i}. {tc['category']} - {tc['message'][:50]}...")
                    print(f"      Error: {result['error']}")

        print("\n" + "="*70)

    async def test_conversation_continuity(self):
        """Test that context is maintained across routing"""
        print("\n\n" + "="*70)
        print("🔄 CONVERSATION CONTINUITY TEST")
        print("="*70)

        session_id = None

        # First message
        print("\n1️⃣ First message (should route to default):")
        result1 = await self.test_single_case({
            "message": "سلام! من علی هستم",
            "expected_agent": "default",
            "category": "Greeting",
            "language": "Persian"
        })

        if result1["success"]:
            session_id = result1.get("session_id")
            print(f"   Session ID: {session_id}")

        await asyncio.sleep(1)

        # Second message - different topic
        print("\n2️⃣ Second message - medical (should route to doctor):")
        result2 = await self.test_single_case({
            "message": "سردرد دارم",
            "expected_agent": "doctor",
            "category": "Medical",
            "language": "Persian"
        }, session_id=session_id)

        # Check if name was remembered
        if result2["success"] and "علی" in result2["response"]:
            print("   ✅ Context maintained! Agent remembered name 'علی'")
        else:
            print("   ⚠️  Context may not be maintained across routing")


async def main():
    """Main test runner"""
    import sys

    # Check if orchestrator is accessible
    print("🔍 Checking if orchestrator is available...")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/agents")
            if response.status_code == 200:
                agents = response.json()
                if "orchestrator" in agents:
                    print("✅ Orchestrator agent found!")
                else:
                    print("❌ Orchestrator not found in agent list")
                    print(f"   Available agents: {list(agents.keys())}")
                    sys.exit(1)
            else:
                print(f"❌ Failed to get agents list: {response.status_code}")
                sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to service: {e}")
        print("   Make sure the service is running on http://localhost:8000")
        sys.exit(1)

    # Run tests
    tester = OrchestratorTester()

    print("\n" + "="*70)
    print("Select test mode:")
    print("1. Run all routing tests")
    print("2. Run conversation continuity test")
    print("3. Run both")
    print("="*70)

    choice = input("Enter choice (1-3) or press Enter for all: ").strip()

    if not choice or choice == "3":
        await tester.test_all()
        await tester.test_conversation_continuity()
    elif choice == "1":
        await tester.test_all()
    elif choice == "2":
        await tester.test_conversation_continuity()
    else:
        print("Invalid choice")
        sys.exit(1)

    print("\n✅ All tests complete!")


if __name__ == "__main__":
    asyncio.run(main())
