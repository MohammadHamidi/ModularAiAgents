"""
Suggestion lifecycle: when to show suggestions, when to switch to free mode, transition message.
Used by both chain executor and chat agent.
"""
from typing import Any, Dict, List, Optional, Tuple


def _turn_count(history: List[Dict[str, Any]]) -> int:
    """Approximate number of conversation turns (user+assistant pair = 1 turn)."""
    if not history:
        return 0
    user_msgs = sum(1 for m in history if m.get("role") == "user")
    return user_msgs


def should_show_suggestions(
    session_state: Optional[Dict[str, Any]],
    history: List[Dict[str, Any]],
    chat_ui_config: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str], bool]:
    """
    Decide whether to append the suggestions block and if we should switch to free mode this turn.

    Returns:
        (show_suggestions, transition_message, switch_to_free)
        - show_suggestions: if False, do not add "پیشنهادهای بعدی" block
        - transition_message: if set, prepend/append this to the response when switching to free
        - switch_to_free: if True, response metadata should set user_mode = "free"
    """
    chat_ui_config = chat_ui_config or {}
    session_state = session_state or {}
    user_mode = session_state.get("user_mode", "guided")
    suggestion_click_count = session_state.get("suggestion_click_count", 0)
    max_clicks = chat_ui_config.get("max_suggestion_clicks_per_session", 3)
    warmup_turns = chat_ui_config.get("suggestion_warmup_turns", 3)
    free_mode_turn_trigger = chat_ui_config.get("free_mode_turn_trigger", 4)
    transition_msg = chat_ui_config.get("transition_to_free_message", "")

    turns = _turn_count(history)
    switch_to_free = False
    show = True

    if user_mode == "free":
        show = False
        return show, None, switch_to_free

    if suggestion_click_count >= max_clicks:
        show = False
        switch_to_free = True
        return show, transition_msg or None, switch_to_free

    if turns >= free_mode_turn_trigger:
        show = False
        switch_to_free = True
        return show, transition_msg or None, switch_to_free

    return show, None, switch_to_free


def get_updated_session_metadata(
    session_state: Dict[str, Any],
    switch_to_free: bool,
) -> Dict[str, Any]:
    """Build metadata dict to return in response so main.py can persist user_mode etc."""
    out = {
        "user_mode": "free" if switch_to_free else session_state.get("user_mode", "guided"),
        "suggestion_click_count": session_state.get("suggestion_click_count", 0),
        "last_message_from_suggestion": session_state.get("last_message_from_suggestion", False),
    }
    return out
