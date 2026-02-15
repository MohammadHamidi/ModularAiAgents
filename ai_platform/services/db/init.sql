-- Initialize database schema for chat service
-- This script is automatically run when PostgreSQL container is first created

-- Create chat_sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    agent_type VARCHAR(255) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create index on agent_type for faster queries
CREATE INDEX IF NOT EXISTS idx_chat_sessions_agent_type ON chat_sessions(agent_type);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at);

-- Create agent_context table
CREATE TABLE IF NOT EXISTS agent_context (
    session_id UUID NOT NULL,
    context_key VARCHAR(255) NOT NULL,
    context_value JSONB NOT NULL,
    agent_type VARCHAR(255),
    expires_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, context_key)
);

-- Create indexes for agent_context
CREATE INDEX IF NOT EXISTS idx_agent_context_session_id ON agent_context(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_context_expires_at ON agent_context(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_context_agent_type ON agent_context(agent_type);

-- Create service_logs table for log viewer (API requests, traces, conversations)
CREATE TABLE IF NOT EXISTS service_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    log_type VARCHAR(50) NOT NULL,
    session_id UUID,
    agent_key VARCHAR(100),
    method VARCHAR(10),
    path VARCHAR(500),
    status_code INTEGER,
    request_headers JSONB,
    request_body JSONB,
    response_summary TEXT,
    response_body TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    duration_ms FLOAT
);

CREATE INDEX IF NOT EXISTS idx_service_logs_created_at ON service_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_service_logs_session_id ON service_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_service_logs_agent_key ON service_logs(agent_key);
CREATE INDEX IF NOT EXISTS idx_service_logs_log_type ON service_logs(log_type);

-- Create chat_feedback table for message-level feedback
CREATE TABLE IF NOT EXISTS chat_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    message_id VARCHAR(255) NOT NULL,
    feedback_type VARCHAR(20) NOT NULL CHECK (feedback_type IN ('like', 'dislike')),
    reason_codes JSONB,
    comment TEXT,
    last_messages JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_feedback_session_id ON chat_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_user_id ON chat_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_message_id ON chat_feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_created_at ON chat_feedback(created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_feedback_idempotent ON chat_feedback(message_id, COALESCE(user_id, ''));

