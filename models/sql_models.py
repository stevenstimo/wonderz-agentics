from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class CrewMemberSQL(Base):
    __tablename__ = 'crew_members'
    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    specialization = Column(String(100))
    status = Column(String(50), nullable=False)
    current_task = Column(String(255))
    progress = Column(Integer, default=0)
    avatar_url = Column(String(255))
    system_instructions = Column(Text)
    knowledge_base_sources = Column(Text)
    tool_access_whitelist = Column(Text)
    hiring_logic = Column(Text)
    persona = Column(Text)
    quality_notes = Column(Text)
    growth = Column(Text)
    development_notes = Column(Text)


class TalentSQL(Base):
    __tablename__ = 'talents'
    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    persona = Column(Text)
    quality = Column(Text)
    growth = Column(Text)
    skills = Column(Text)  # JSON string: [{"name": "Python", "level": 3}, ...]
    avatar_url = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class SettingsSQL(Base):
    __tablename__ = 'settings'
    id = Column(String, primary_key=True, default='default')
    gemini_api_key = Column(Text)
    anthropic_api_key = Column(Text)
    supabase_url = Column(Text)
    supabase_key = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
