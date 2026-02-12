from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base

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


# TalentSQL: alleen profiel, skills, avatar, aanmaakdatum
from sqlalchemy import DateTime
from datetime import datetime

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
