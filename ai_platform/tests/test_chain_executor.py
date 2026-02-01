"""
Integration tests for chain-based executor.
Run with: pytest tests/test_chain_executor.py -v
Requires: EXECUTOR_MODE=langchain_chain, chat service running, or mock tools.
"""
import os
import pytest


def test_api_contract_agent_request():
    """Verify AgentRequest schema matches API contract."""
    from shared.base_agent import AgentRequest
    r = AgentRequest(message="test", session_id=None, use_shared_context=True)
    assert r.message == "test"
    assert r.use_shared_context is True
    assert "message" in AgentRequest.model_fields
    assert "session_id" in AgentRequest.model_fields


def test_api_contract_agent_response():
    """Verify AgentResponse schema matches API contract."""
    from shared.base_agent import AgentResponse
    r = AgentResponse(session_id="x", output="out", metadata={}, context_updates={})
    assert r.session_id == "x"
    assert r.output == "out"
    assert "session_id" in AgentResponse.model_fields
    assert "output" in AgentResponse.model_fields
    assert "metadata" in AgentResponse.model_fields
    assert "context_updates" in AgentResponse.model_fields


def test_prompt_builder_import():
    """Verify shared prompt builder is importable."""
    from shared.prompt_builder import build_system_prompt, build_context_summary
    assert callable(build_system_prompt)
    assert callable(build_context_summary)


def test_config_loader_executor_mode():
    """Verify ConfigLoader returns chain-mode prompt when executor_mode=langchain_chain."""
    # Config loader resolves paths relative to its config dir (chat-service/config)
    from agents.config_loader import load_agent_config
    config = load_agent_config("personalities/guest_faq.yaml")
    prompt_agentic = config.get_complete_system_prompt(executor_mode="pydantic_ai")
    prompt_chain = config.get_complete_system_prompt(executor_mode="langchain_chain")
    assert "CONTEXT PROVIDED BY SYSTEM" in prompt_chain
    assert "save_user_info" in prompt_agentic or "knowledge_base" in prompt_agentic.lower()
