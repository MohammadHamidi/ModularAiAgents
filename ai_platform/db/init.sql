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

