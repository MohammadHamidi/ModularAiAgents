import os

# Configurable retention for session history and context
MAX_SESSION_MESSAGES: int = int(os.getenv("MAX_SESSION_MESSAGES", "30"))
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "14400"))  # 4 hours


