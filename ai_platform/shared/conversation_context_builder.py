"""
Conversation context builder - Handles summarization for long sessions.
When history exceeds threshold, summarizes older messages and keeps recent ones.
Uses cached incremental summarization stored in session metadata.
"""
import os
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SUMMARIZE_THRESHOLD = int(os.getenv("SUMMARIZE_THRESHOLD", "10"))
KEEP_LAST_N = int(os.getenv("KEEP_LAST_N", "2"))  # Number of user messages to keep


def _extract_recent_messages(
    messages: List[Dict[str, Any]],
    keep_user_count: int,
) -> List[Dict[str, Any]]:
    """Extract messages containing the last keep_user_count user messages."""
    if not messages:
        return []
    user_indices = [
        i for i, m in enumerate(messages)
        if m.get("role") == "user"
    ]
    if not user_indices:
        return messages[-4:]  # Fallback
    start_idx = user_indices[-keep_user_count] if len(user_indices) >= keep_user_count else 0
    return messages[start_idx:]


async def build_history_context(
    messages: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    summarizer,  # ConversationSummarizerChain instance
    threshold: int = SUMMARIZE_THRESHOLD,
    keep_last_n: int = KEEP_LAST_N,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Build effective history and context for the chain.

    When len(messages) <= threshold: returns full history, no summary.
    When len(messages) > threshold: uses cached summary or runs summarizer,
    returns (recent_messages, summary_block, updated_metadata).

    Caller is responsible for persisting updated_metadata to the session.

    Args:
        messages: Full message list from session
        metadata: Session metadata (may contain conversation_summary, summary_up_to_index)
        summarizer: ConversationSummarizerChain instance
        threshold: Message count threshold for summarization
        keep_last_n: Number of user messages to keep as recent

    Returns:
        (effective_history, summary_block, updated_metadata)
        - effective_history: Messages to pass to SpecialistChain (recent ones for KB)
        - summary_block: String to append to context_block (empty if no summary)
        - updated_metadata: Metadata with new summary if we ran summarization
    """
    meta = dict(metadata) if metadata else {}
    summary_block = ""

    if not messages or len(messages) <= threshold:
        return messages, "", meta

    recent = _extract_recent_messages(messages, keep_last_n)
    to_summarize_end = len(messages) - len(recent)
    if to_summarize_end <= 0:
        return messages, "", meta

    existing_summary = meta.get("conversation_summary") or ""
    summary_up_to = meta.get("summary_up_to_index", -1)

    to_summarize: List[Dict[str, Any]] = []
    if summary_up_to >= 0 and existing_summary:
        start = summary_up_to + 1
        if start < to_summarize_end:
            to_summarize = messages[start:to_summarize_end]
    else:
        to_summarize = messages[:to_summarize_end]

    if to_summarize:
        new_summary = await summarizer.summarize(to_summarize, existing_summary)
        meta["conversation_summary"] = new_summary
        meta["summary_up_to_index"] = to_summarize_end - 1
        summary_block = f"\n\n[خلاصه مکالمه قبلی]\n{new_summary}"

    return recent, summary_block, meta
