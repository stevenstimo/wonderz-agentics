"""
Configuratie voor het Multi-Agent Development System
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Configuratie
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# Agent Configuratie
AGENT_CONFIG = {
    "product_owner": {
        "model": MODEL_NAME,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
    },
    "developer": {
        "model": MODEL_NAME,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.3,  # Lager voor meer deterministische code
    },
    "reviewer": {
        "model": MODEL_NAME,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.5,
    },
    "devops": {
        "model": MODEL_NAME,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.4,
    },
}

# Output directories
OUTPUT_DIR = "output"
REQUIREMENTS_DIR = f"{OUTPUT_DIR}/requirements"
CODE_DIR = f"{OUTPUT_DIR}/code"
REVIEW_DIR = f"{OUTPUT_DIR}/reviews"
DEVOPS_DIR = f"{OUTPUT_DIR}/devops"

# Maak directories aan
for directory in [OUTPUT_DIR, REQUIREMENTS_DIR, CODE_DIR, REVIEW_DIR, DEVOPS_DIR]:
    os.makedirs(directory, exist_ok=True)
