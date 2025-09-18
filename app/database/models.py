# app/database/models.py - 修正版

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

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
    """抽出単語テーブル（拡張版）"""
    __tablename__ = "extracted_words"
    
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False, index=True)
    word_type = Column(String(50))  # 名詞、固有名詞など
    part_of_speech = Column(String(50))  # 品詞詳細（MeCab用）
    frequency = Column(Integer, default=1)
    importance_score = Column(Float, default=0.0)  # 重要度スコア
    source_article_id = Column(Integer, ForeignKey('news_articles.id'))
    context = Column(Text)  # 出現文脈
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # リレーション
    source_article = relationship("NewsArticle", backref="extracted_words")

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