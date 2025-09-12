from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database.database import Base

class NewsArticle(Base):
    """ニュース記事モデル"""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    url = Column(String(512), unique=True, nullable=False)
    source = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<NewsArticle(title='{self.title[:30]}...', source='{self.source}')>"