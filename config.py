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

# ===== IMPORTANTE URLs & ENDPOINTS =====
# Maak het makkelijk om alle URLs te gebruiken zonder steeds opnieuw in te voeren!

class AppConfig:
    """Centralized configuration for all important URLs"""
    
    # Development URLs
    BACKEND_DEV = "http://localhost:8090"
    FRONTEND_DEV = "http://localhost:5173"
    
    # Production URLs (exe.dev server)
    BACKEND_PROD = "https://wonderz-agentic.exe.xyz"
    FRONTEND_PROD = "https://frontend-rho-one-99.vercel.app"
    
    # Database
    DATABASE_HOST = "localhost"
    DATABASE_PORT = 5432
    DATABASE_NAME = "postgres"
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"postgresql://postgres:postgres@localhost:5432/postgres"
    )
    
    # Use production or development URLs
    USE_PRODUCTION = os.getenv("ENV", "development").lower() == "production"
    
    BACKEND_URL = BACKEND_PROD if USE_PRODUCTION else BACKEND_DEV
    FRONTEND_URL = FRONTEND_PROD if USE_PRODUCTION else FRONTEND_DEV
    
    # API Endpoints
    API_ENDPOINTS = {
        "crew": "/api/crew",
        "projects": "/api/projects",
        "jobs": "/jobs",
        "tasks": "/api/task",
        "unified_products": "/api/unified-products",
        "docs": "/docs",
        "health": "/health",
    }
    
    @classmethod
    def get_api_url(cls, endpoint: str = "") -> str:
        """Get full API URL"""
        return f"{cls.BACKEND_URL}{endpoint}"
    
    @classmethod
    def get_frontend_url(cls, path: str = "") -> str:
        """Get full frontend URL"""
        return f"{cls.FRONTEND_URL}{path}"
    
    @classmethod
    def print_config(cls):
        """Print all important URLs"""
        print("\n" + "="*60)
        print("🔗 IMPORTANT URLs - AI Bureau")
        print("="*60)
        print(f"Backend API:     {cls.BACKEND_URL}")
        print(f"Frontend:        {cls.FRONTEND_URL}")
        print(f"Database:        {cls.DATABASE_HOST}:{cls.DATABASE_PORT}")
        print(f"Environment:     {'PRODUCTION' if cls.USE_PRODUCTION else 'DEVELOPMENT'}")
        print("="*60)
        print("\n📚 API Endpoints:")
        for name, endpoint in cls.API_ENDPOINTS.items():
            full_url = cls.get_api_url(endpoint)
            print(f"  {name:20} -> {full_url}")
        print("="*60 + "\n")
