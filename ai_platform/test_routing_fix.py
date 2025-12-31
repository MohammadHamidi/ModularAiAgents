"""
Quick test to verify orchestrator routing fix
"""
import asyncio
import httpx
import sys

# Fix Unicode encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

GATEWAY_URL = "http://localhost:8003"

# Test questions that should be routed
test_questions = [
    {
        "num": 5,
        "text": "منظور از «کُنش» توی این سیستم چیه؟ یه کم کلمه سختیه، میشه توضیح بدی؟",
        "expected_agent": "action_expert or guest_faq"
    },
    {
        "num": 2,
        "text": "من دقیقاً نمی‌دونم «سفیر آیه‌ها» یعنی چی؟ تعریف شما چیه و باید چه ویژگی‌هایی داشته باشم؟",
        "expected_agent": "guest_faq"
    },
    {
        "num": 16,
        "text": "من تو خونه می‌خوام کار کنم ولی نمی‌دونم چی کار کنم. پیشنهاد ویژه‌ت چیه؟",
        "expected_agent": "action_expert"
    }
]

# Patterns that indicate orchestrator is adding explanatory text (should NOT appear)
bad_patterns = [
    "از آنجایی که",
    "من درخواست شما را",
    "ارجاع دادم",
    "متخصص پاسخ داد",
    "به متخصص",
    "ابزار",
    "راهکاری که انتخاب"
]

async def test_question(client: httpx.AsyncClient, question: dict) -> dict:
    """Test a single question"""
    try:
        response = await client.post(
            f"{GATEWAY_URL}/chat/orchestrator",
            json={
                "message": question["text"],
                "use_shared_context": True
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            result = response.json()
            output = result.get("output", "")
            
            # Check for bad patterns
            found_bad_patterns = []
            for pattern in bad_patterns:
                if pattern in output:
                    found_bad_patterns.append(pattern)
            
            return {
                "success": True,
                "question_num": question["num"],
                "question": question["text"][:60] + "...",
                "response_length": len(output),
                "response_preview": output[:200] + "..." if len(output) > 200 else output,
                "has_routing_explanation": len(found_bad_patterns) > 0,
                "bad_patterns_found": found_bad_patterns
            }
        else:
            return {
                "success": False,
                "question_num": question["num"],
                "error": f"HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "success": False,
            "question_num": question["num"],
            "error": str(e)
        }

async def main():
    """Run tests"""
    print("Testing orchestrator routing fix...")
    print("=" * 80)
    
    async with httpx.AsyncClient() as client:
        # Test health
        try:
            health = await client.get(f"{GATEWAY_URL}/health", timeout=5.0)
            if health.status_code == 200:
                print("✓ Service is healthy\n")
            else:
                print(f"⚠ Health check returned {health.status_code}\n")
        except Exception as e:
            print(f"✗ Service health check failed: {e}\n")
            return
        
        # Test questions
        results = []
        for question in test_questions:
            print(f"\nTesting Question {question['num']}:")
            print(f"  Q: {question['text'][:60]}...")
            
            result = await test_question(client, question)
            results.append(result)
            
            if result["success"]:
                print(f"  ✓ Got response ({result['response_length']} chars)")
                
                if result["has_routing_explanation"]:
                    print(f"  ✗ FOUND ROUTING EXPLANATION (BAD):")
                    for pattern in result["bad_patterns_found"]:
                        print(f"      - '{pattern}'")
                    print(f"  Response preview: {result['response_preview']}")
                else:
                    print(f"  ✓ No routing explanation (GOOD)")
                    print(f"  Response preview: {result['response_preview']}")
            else:
                print(f"  ✗ Failed: {result['error']}")
            
            # Small delay between requests
            await asyncio.sleep(1)
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        successful = sum(1 for r in results if r.get("success"))
        clean_responses = sum(1 for r in results if r.get("success") and not r.get("has_routing_explanation"))
        
        print(f"Total questions: {len(results)}")
        print(f"Successful: {successful}/{len(results)}")
        print(f"Clean responses (no routing explanation): {clean_responses}/{successful}")
        
        if clean_responses == successful:
            print("\n✓✓✓ ALL RESPONSES ARE CLEAN - FIX WORKING!")
        else:
            print(f"\n✗✗✗ {successful - clean_responses} responses still have routing explanations")

if __name__ == "__main__":
    asyncio.run(main())

