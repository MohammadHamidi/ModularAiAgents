"""
Load and serve few-shot Q&A examples from the 49 Q&A document.
Used to inject canonical answer format into agent prompts.
"""
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Mapping: agent_key -> list of question numbers (1-49) to use as examples
# Sections: 1-10 (مبانی), 11-15 (محفل), 16-20 (خانه), 21-25 (مسجد),
# 26-30 (مدرسه), 31-40 (مجازی/کار), 41-49 (جمع‌بندی)
AGENT_QA_MAPPING: Dict[str, List[int]] = {
    "guest_faq": [1, 2, 5, 7, 9, 50],  # نهضت، سفیر، کنش، دستیار، وقت، اینجا/داستان چیه
    "action_expert": [11, 16, 22, 27, 35],  # محفل، خانه، مسجد، مدرسه، کلیپ
    "journey_register": [45, 41, 42],  # ثبت کنش، دعوت، کار خیر
    "rewards_invite": [4, 45, 48],  # جایزه، ثبت، ارتقا
    "konesh_expert": [5, 6, 16, 21],  # کنش، کنش ویژه، خانه، مسجد
    "friendly_tutor": [2, 7, 9],  # سفیر، دستیار، وقت
    "professional_assistant": [1, 3, 8],  # نهضت، هدف، کتاب
    "minimal_assistant": [1, 2, 5],  # core FAQ
    "orchestrator": [1, 2, 7],  # general routing examples
}

DEFAULT_MAX_EXAMPLES = 5

# Fallback for unknown agents: use guest_faq examples
DEFAULT_AGENT = "guest_faq"


def _find_qa_file() -> Optional[Path]:
    """Find QA_EXAMPLES.md in project root."""
    candidates = [
        Path("/app/QA_EXAMPLES.md"),  # Docker
        Path(__file__).resolve().parent.parent / "QA_EXAMPLES.md",  # ai_platform root
        Path(__file__).resolve().parent.parent.parent / "QA_EXAMPLES.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# Persian/Arabic digit to ASCII
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _parse_qa_file(content: str) -> Dict[int, Tuple[str, str]]:
    """
    Parse QA_EXAMPLES.md content into {question_num: (question, answer)}.
    Format: سوال N: ... \\n پاسخ: ...
    """
    result: Dict[int, Tuple[str, str]] = {}
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"سوال\s*([\d۰-۹]+)\s*:\s*(.+)", line)
        if match:
            num_str = match.group(1).translate(_PERSIAN_DIGITS)
            num = int(num_str) if num_str.isdigit() else 0
            q_text = match.group(2).strip()
            i += 1
            answer_parts = []
            while i < len(lines):
                next_line = lines[i]
                if re.match(r"پاسخ\s*:\s*", next_line):
                    ans_match = re.match(r"پاسخ\s*:\s*(.+)", next_line)
                    if ans_match:
                        answer_parts.append(ans_match.group(1).strip())
                    i += 1
                    while i < len(lines):
                        curr = lines[i]
                        if re.match(r"سوال\s*\d+\s*:", curr):
                            break
                        if curr.strip().startswith("بخش ") or curr.strip().startswith("_" * 5):
                            break
                        if curr.strip():
                            answer_parts.append(curr.strip())
                        i += 1
                    break
                i += 1
            answer = " ".join(answer_parts) if answer_parts else ""
            if q_text and answer:
                result[num] = (q_text, answer)
            continue
        i += 1
    return result


_cached_qa: Optional[Dict[int, Tuple[str, str]]] = None


def _load_qa() -> Dict[int, Tuple[str, str]]:
    """Load and cache parsed Q&A pairs."""
    global _cached_qa
    if _cached_qa is not None:
        return _cached_qa
    path = _find_qa_file()
    if not path:
        logger.warning("QA_EXAMPLES.md not found; few-shot examples disabled")
        _cached_qa = {}
        return _cached_qa
    try:
        content = path.read_text(encoding="utf-8")
        _cached_qa = _parse_qa_file(content)
        logger.info("Loaded %d Q&A pairs from QA_EXAMPLES.md", len(_cached_qa))
    except Exception as e:
        logger.warning("Failed to load QA_EXAMPLES.md: %s", e)
        _cached_qa = {}
    return _cached_qa


def get_few_shot_examples(
    agent_key: str,
    max_examples: int = DEFAULT_MAX_EXAMPLES,
) -> str:
    """
    Return formatted few-shot examples for the given agent.

    Returns a string to append to the system prompt, or empty if none available.
    """
    qa = _load_qa()
    if not qa:
        return ""
    indices = AGENT_QA_MAPPING.get(agent_key) or AGENT_QA_MAPPING.get(DEFAULT_AGENT) or []
    if not indices:
        return ""
    examples = []
    for num in indices[:max_examples]:
        if num in qa:
            q, a = qa[num]
            examples.append(f"سوال: {q}\nپاسخ: {a}")
    if not examples:
        return ""
    header = "📋 مثال‌های پاسخ صحیح (همین سبک و لحن را رعایت کن):\n\n"
    return header + "\n\n---\n\n".join(examples)
