from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime
from app.database.database import Base

class OgiriTopic(Base):
    """大喜利お題モデル"""
    __tablename__ = "ogiri_topics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class TrainingTopic(Base):
    """トレーニング用お題モデル"""
    __tablename__ = "training_topics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)