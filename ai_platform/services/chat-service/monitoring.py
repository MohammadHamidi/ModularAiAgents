# services/chat-service/monitoring.py
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionTrace:
    """Complete trace of a single agent execution"""
    session_id: str
    agent_key: str
    agent_name: str
    timestamp: datetime

    # Input
    system_prompt: str
    user_message_original: str
    user_message_final: str  # After context injection
    shared_context: Dict[str, Any]
    message_history_count: int

    # KB Operations
    kb_queries: List[Dict[str, Any]] = field(default_factory=list)
    kb_results: List[Dict[str, Any]] = field(default_factory=list)

    # Tool Calls
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    # LLM Interaction
    llm_input_full: str = ""  # Complete prompt sent to LLM
    llm_output_raw: str = ""  # Raw LLM response

    # Routing
    routing_decision: Optional[Dict[str, Any]] = None

    # Output
    final_response: str = ""
    post_processing_applied: List[str] = field(default_factory=list)

    # Performance
    execution_time_ms: float = 0.0

    # Metadata
    trace_id: Optional[str] = None  # Unique ID for this trace

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "agent_key": self.agent_key,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp.isoformat(),
            "system_prompt": self.system_prompt,
            "user_message_original": self.user_message_original,
            "user_message_final": self.user_message_final,
            "shared_context": self.shared_context,
            "message_history_count": self.message_history_count,
            "kb_queries": self.kb_queries,
            "kb_results": self.kb_results,
            "tool_calls": self.tool_calls,
            "llm_input_full": self.llm_input_full,
            "llm_output_raw": self.llm_output_raw,
            "routing_decision": self.routing_decision,
            "final_response": self.final_response,
            "post_processing_applied": self.post_processing_applied,
            "execution_time_ms": self.execution_time_ms
        }


class TraceCollector:
    """Collects execution traces in memory (can be extended to database)"""

    def __init__(self, max_traces: int = 1000):
        self.traces: List[ExecutionTrace] = []
        self.max_traces = max_traces
        self._trace_counter = 0

    def add_trace(self, trace: ExecutionTrace):
        """Add a trace, maintaining max size"""
        # Assign unique ID
        self._trace_counter += 1
        trace.trace_id = f"trace_{self._trace_counter}"

        self.traces.append(trace)

        # Maintain max size (FIFO)
        if len(self.traces) > self.max_traces:
            removed = self.traces.pop(0)
            logger.debug(f"Removed oldest trace: {removed.trace_id}")

        logger.debug(f"Added trace {trace.trace_id} for session {trace.session_id}")

    def get_traces(
        self,
        session_id: Optional[str] = None,
        agent_key: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get traces, optionally filtered by session or agent"""
        traces = self.traces

        # Filter by session_id
        if session_id:
            traces = [t for t in traces if t.session_id == session_id]

        # Filter by agent_key
        if agent_key:
            traces = [t for t in traces if t.agent_key == agent_key]

        # Return most recent traces up to limit
        return [t.to_dict() for t in traces[-limit:]]

    def get_trace_by_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific trace by ID"""
        for trace in self.traces:
            if trace.trace_id == trace_id:
                return trace.to_dict()
        return None

    def get_trace_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get a specific trace by index (for backward compatibility)"""
        if 0 <= index < len(self.traces):
            return self.traces[index].to_dict()
        return None

    def get_recent_traces(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get the most recent N traces"""
        return [t.to_dict() for t in self.traces[-count:]]

    def clear_traces(self):
        """Clear all traces"""
        self.traces.clear()
        self._trace_counter = 0
        logger.info("Cleared all traces")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about collected traces"""
        if not self.traces:
            return {
                "total_traces": 0,
                "agents": {},
                "avg_execution_time_ms": 0
            }

        agent_counts = {}
        total_time = 0

        for trace in self.traces:
            agent_counts[trace.agent_key] = agent_counts.get(trace.agent_key, 0) + 1
            total_time += trace.execution_time_ms

        return {
            "total_traces": len(self.traces),
            "agents": agent_counts,
            "avg_execution_time_ms": total_time / len(self.traces) if self.traces else 0,
            "oldest_trace": self.traces[0].timestamp.isoformat() if self.traces else None,
            "newest_trace": self.traces[-1].timestamp.isoformat() if self.traces else None
        }


# Global collector instance
trace_collector = TraceCollector(max_traces=1000)
