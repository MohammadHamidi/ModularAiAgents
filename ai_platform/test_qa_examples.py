"""
Test script for QA_EXAMPLES.md questions
Tests the service with all 49 questions and analyzes behavior
"""
import asyncio
import httpx
import json
import re
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

# Fix Unicode encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8003")  # Default port from docker-compose
AGENT_KEY = os.getenv("AGENT_KEY", "orchestrator")  # Use orchestrator for intelligent routing
QA_FILE = Path(__file__).parent / "QA_EXAMPLES.md"

# Statistics
stats = {
    "total_questions": 0,
    "successful": 0,
    "failed": 0,
    "errors": [],
    "response_times": [],
    "response_lengths": [],
    "questions_by_section": {}
}

def extract_questions_from_md(file_path: Path) -> List[Dict[str, str]]:
    """Extract all questions from QA_EXAMPLES.md"""
    questions = []
    current_section = None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Persian/Farsi number mapping
    persian_numbers = {
        '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5',
        '۶': '6', '۷': '7', '۸': '8', '۹': '9', '۰': '0'
    }
    
    def convert_persian_number(text: str) -> str:
        """Convert Persian numbers to Arabic"""
        result = text
        for persian, arabic in persian_numbers.items():
            result = result.replace(persian, arabic)
        return result
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Check for section header
        if line.startswith('بخش'):
            # Extract section name
            section_match = re.match(r'بخش\s+(.+?):\s*(.+?)(?:\s*\(.+?\))?$', line)
            if section_match:
                current_section = section_match.group(1).strip() + ': ' + section_match.group(2).strip()
            else:
                current_section = line
            i += 1
            continue
        
        # Check for question (format: سوال ۱: or سوال 1:)
        question_match = re.match(r'سوال\s+([۰-۹0-9]+):\s*(.+)$', line)
        if question_match:
            q_num_str = convert_persian_number(question_match.group(1))
            try:
                q_num = int(q_num_str)
            except ValueError:
                # Try to extract number from Persian
                q_num = 0
                for char in q_num_str:
                    if char.isdigit():
                        q_num = q_num * 10 + int(char)
            
            q_text = question_match.group(2).strip()
            
            # Clean up question text (remove extra whitespace)
            q_text = re.sub(r'\s+', ' ', q_text)
            
            questions.append({
                "number": q_num,
                "text": q_text,
                "section": current_section or "Unknown"
            })
        
        i += 1
    
    # Sort by question number
    questions.sort(key=lambda x: x["number"])
    
    return questions

async def test_question(
    client: httpx.AsyncClient,
    question: Dict[str, str],
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Test a single question and return results"""
    start_time = time.time()
    
    try:
        # Prepare request
        request_data = {
            "message": question["text"],
            "use_shared_context": True
        }
        # Only include session_id if it's not None
        if session_id:
            request_data["session_id"] = session_id
        
        # Send request
        response = await client.post(
            f"{GATEWAY_URL}/chat/{AGENT_KEY}",
            json=request_data,
            timeout=60.0
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "question_num": question["number"],
                "question": question["text"],
                "section": question["section"],
                "response": result.get("output", ""),
                "session_id": result.get("session_id"),
                "suggestions": result.get("suggestions", []),
                "metadata": result.get("metadata", {}),
                "response_time": elapsed_time,
                "response_length": len(result.get("output", "")),
                "status_code": response.status_code
            }
        else:
            return {
                "success": False,
                "question_num": question["number"],
                "question": question["text"],
                "section": question["section"],
                "error": f"HTTP {response.status_code}: {response.text}",
                "response_time": elapsed_time,
                "status_code": response.status_code
            }
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        return {
            "success": False,
            "question_num": question["number"],
            "question": question["text"],
            "section": question["section"],
            "error": str(e),
            "response_time": elapsed_time
        }

async def test_all_questions(questions: List[Dict[str, str]], max_concurrent: int = 3) -> List[Dict[str, Any]]:
    """Test all questions with rate limiting"""
    results = []
    session_id = None  # Use same session for all questions to test context
    
    async with httpx.AsyncClient() as client:
        # Test questions in batches to avoid overwhelming the service
        for i in range(0, len(questions), max_concurrent):
            batch = questions[i:i + max_concurrent]
            batch_tasks = [test_question(client, q, session_id) for q in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results.append({
                        "success": False,
                        "error": str(result)
                    })
                else:
                    results.append(result)
                    if result.get("success") and result.get("session_id"):
                        session_id = result["session_id"]  # Use same session for context
            
            # Small delay between batches
            if i + max_concurrent < len(questions):
                await asyncio.sleep(1)
    
    return results

def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze test results and generate statistics"""
    analysis = {
        "total": len(results),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "avg_response_time": 0,
        "avg_response_length": 0,
        "errors": [],
        "by_section": {},
        "response_quality": {
            "too_short": 0,  # < 50 chars
            "short": 0,      # 50-200 chars
            "medium": 0,    # 200-500 chars
            "long": 0,      # > 500 chars
        }
    }
    
    successful_results = [r for r in results if r.get("success")]
    
    if successful_results:
        response_times = [r["response_time"] for r in successful_results]
        response_lengths = [r["response_length"] for r in successful_results]
        
        analysis["avg_response_time"] = sum(response_times) / len(response_times)
        analysis["avg_response_length"] = sum(response_lengths) / len(response_lengths)
        
        # Categorize by length
        for length in response_lengths:
            if length < 50:
                analysis["response_quality"]["too_short"] += 1
            elif length < 200:
                analysis["response_quality"]["short"] += 1
            elif length < 500:
                analysis["response_quality"]["medium"] += 1
            else:
                analysis["response_quality"]["long"] += 1
        
        # Group by section
        for result in successful_results:
            section = result.get("section", "Unknown")
            if section not in analysis["by_section"]:
                analysis["by_section"][section] = {
                    "total": 0,
                    "successful": 0,
                    "avg_response_time": 0,
                    "avg_response_length": 0
                }
            analysis["by_section"][section]["total"] += 1
            if result.get("success"):
                analysis["by_section"][section]["successful"] += 1
                # Update averages
                section_results = [r for r in successful_results if r.get("section") == section]
                if section_results:
                    analysis["by_section"][section]["avg_response_time"] = \
                        sum(r["response_time"] for r in section_results) / len(section_results)
                    analysis["by_section"][section]["avg_response_length"] = \
                        sum(r["response_length"] for r in section_results) / len(section_results)
    
    # Collect errors
    for result in results:
        if not result.get("success"):
            analysis["errors"].append({
                "question_num": result.get("question_num"),
                "question": result.get("question", "")[:100],
                "error": result.get("error", "Unknown error")
            })
    
    return analysis

def generate_report(results: List[Dict[str, Any]], analysis: Dict[str, Any]) -> str:
    """Generate a detailed test report"""
    report = []
    report.append("=" * 80)
    report.append("QA_EXAMPLES.md Test Report")
    report.append("=" * 80)
    report.append(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Gateway URL: {GATEWAY_URL}")
    report.append(f"Agent Key: {AGENT_KEY}")
    report.append("")
    
    # Summary Statistics
    report.append("SUMMARY STATISTICS")
    report.append("-" * 80)
    report.append(f"Total Questions: {analysis['total']}")
    report.append(f"Successful: {analysis['successful']} ({analysis['successful']/analysis['total']*100:.1f}%)")
    report.append(f"Failed: {analysis['failed']} ({analysis['failed']/analysis['total']*100:.1f}%)")
    report.append(f"Average Response Time: {analysis['avg_response_time']:.2f}s")
    report.append(f"Average Response Length: {analysis['avg_response_length']:.0f} characters")
    report.append("")
    
    # Response Quality
    report.append("RESPONSE QUALITY DISTRIBUTION")
    report.append("-" * 80)
    quality = analysis["response_quality"]
    total_successful = analysis["successful"]
    if total_successful > 0:
        report.append(f"Too Short (<50 chars): {quality['too_short']} ({quality['too_short']/total_successful*100:.1f}%)")
        report.append(f"Short (50-200 chars): {quality['short']} ({quality['short']/total_successful*100:.1f}%)")
        report.append(f"Medium (200-500 chars): {quality['medium']} ({quality['medium']/total_successful*100:.1f}%)")
        report.append(f"Long (>500 chars): {quality['long']} ({quality['long']/total_successful*100:.1f}%)")
    report.append("")
    
    # By Section
    if analysis["by_section"]:
        report.append("RESULTS BY SECTION")
        report.append("-" * 80)
        for section, stats in analysis["by_section"].items():
            report.append(f"\n{section}:")
            report.append(f"  Total: {stats['total']}")
            report.append(f"  Successful: {stats['successful']}")
            if stats['successful'] > 0:
                report.append(f"  Avg Response Time: {stats['avg_response_time']:.2f}s")
                report.append(f"  Avg Response Length: {stats['avg_response_length']:.0f} chars")
    report.append("")
    
    # Errors
    if analysis["errors"]:
        report.append("ERRORS")
        report.append("-" * 80)
        for error in analysis["errors"][:10]:  # Show first 10 errors
            report.append(f"\nQuestion {error['question_num']}:")
            report.append(f"  Question: {error['question'][:80]}...")
            report.append(f"  Error: {error['error']}")
        if len(analysis["errors"]) > 10:
            report.append(f"\n... and {len(analysis['errors']) - 10} more errors")
    report.append("")
    
    # Sample Responses
    report.append("SAMPLE RESPONSES")
    report.append("-" * 80)
    successful_results = [r for r in results if r.get("success")][:5]
    for result in successful_results:
        report.append(f"\nQuestion {result['question_num']} ({result.get('section', 'Unknown')}):")
        report.append(f"  Q: {result['question'][:100]}...")
        report.append(f"  A: {result['response'][:200]}...")
        report.append(f"  Time: {result['response_time']:.2f}s, Length: {result['response_length']} chars")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)

async def main():
    """Main test function"""
    print("Loading questions from QA_EXAMPLES.md...")
    
    if not QA_FILE.exists():
        print(f"Error: QA_EXAMPLES.md not found at {QA_FILE}")
        return
    
    questions = extract_questions_from_md(QA_FILE)
    print(f"Extracted {len(questions)} questions")
    
    if not questions:
        print("Error: No questions found in QA_EXAMPLES.md")
        return
    
    # Check service health
    print(f"\nChecking service health at {GATEWAY_URL}...")
    try:
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{GATEWAY_URL}/health", timeout=5.0)
            if health_response.status_code == 200:
                health_data = health_response.json()
                print(f"Service is healthy: {health_data}")
            else:
                print(f"Warning: Health check returned {health_response.status_code}")
    except Exception as e:
        print(f"Warning: Could not check service health: {e}")
        print("Continuing with tests anyway...")
    
    # Run tests
    print(f"\nTesting {len(questions)} questions with agent '{AGENT_KEY}'...")
    print("This may take several minutes...\n")
    
    results = await test_all_questions(questions, max_concurrent=3)
    
    # Analyze results
    print("\nAnalyzing results...")
    analysis = analyze_results(results)
    
    # Generate report
    report = generate_report(results, analysis)
    print("\n" + report)
    
    # Save detailed results to JSON
    output_file = Path(__file__).parent / f"qa_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "test_date": datetime.now().isoformat(),
                "gateway_url": GATEWAY_URL,
                "agent_key": AGENT_KEY,
                "total_questions": len(questions)
            },
            "analysis": analysis,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")
    
    # Save report to file
    report_file = Path(__file__).parent / f"qa_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Report saved to: {report_file}")

if __name__ == "__main__":
    asyncio.run(main())

