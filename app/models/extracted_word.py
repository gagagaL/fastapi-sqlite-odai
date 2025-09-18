from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base

class ExtractedWord(Base):
    """抽出された単語モデル"""
    __tablename__ = "extracted_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(255), nullable=False)
    word_type = Column(String(50))
    part_of_speech = Column(String(50))
    frequency = Column(Integer, default=1)
    importance_score = Column(Float, default=0.0)
    source_article_id = Column(Integer, ForeignKey('news_articles.id'))
    context = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    article = relationship("NewsArticle", back_populates="extracted_words")