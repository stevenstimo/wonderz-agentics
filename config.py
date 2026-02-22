import os

# Try to load .env if available, but don't fail if not
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system environment

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://wonderz:wonderz123@localhost:5432/wonderz")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Agent Config (if needed)
AGENT_CONFIG = {}
