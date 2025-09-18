from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from .connection import Base

class NewsArticle(Base):
    """ニュース記事テーブル"""
    __tablename__ = "news_articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    url = Column(String(1000))
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NewsArticle(id={self.id}, title='{self.title[:50]}...')>"

class ExtractedWord(Base):
    """抽出単語テーブル"""
    __tablename__ = "extracted_words"
    
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False, index=True)
    word_type = Column(String(50))  # 名詞、固有名詞など
    frequency = Column(Integer, default=1)
    source_article_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ExtractedWord(word='{self.word}', type='{self.word_type}')>"

class OgiriTopic(Base):
    """大喜利お題テーブル"""
    __tablename__ = "ogiri_topics"
    
    id = Column(Integer, primary_key=True, index=True)
    topic_text = Column(Text, nullable=False)
    is_generated = Column(Boolean, default=False)  # 自動生成かどうか
    used_words = Column(Text)  # 使用した単語（JSON形式）
    rating = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<OgiriTopic(id={self.id}, text='{self.topic_text[:30]}...')>"

class TrainingTopic(Base):
    """学習用お題テーブル"""
    __tablename__ = "training_topics"
    
    id = Column(Integer, primary_key=True, index=True)
    topic_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TrainingTopic(id={self.id}, text='{self.topic_text[:30]}...')>"


class DisplayWord(Base):
    """表示用単語テーブル"""
    __tablename__ = "display_words"
    
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False)
    pos = Column(String(50))  # 追加: 品詞
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<DisplayWord(id={self.id}, word='{self.word}')>"