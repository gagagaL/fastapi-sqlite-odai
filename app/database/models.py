from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from .connection import Base


class DisplayWord(Base):
    """表示用単語テーブル"""

    __tablename__ = "display_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False)
    pos = Column(String(50))  # 追加: 品詞
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DisplayWord(id={self.id}, word='{self.word}')>"


class ConfirmedOdai(Base):
    """確定お題テーブル"""

    __tablename__ = "confirmed_odais"

    id = Column(Integer, primary_key=True, index=True)
    odai_text = Column(Text, nullable=False)
    source = Column(String(50), default="manual")  # manual, generated
    is_active = Column(Boolean, default=False)  # 現在出題中かどうか
    quality_score = Column(Float, default=0.0)  # 品質スコア
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ConfirmedOdai(id={self.id}, text='{self.odai_text[:30]}...')>"


class OdaiRating(Base):
    """お題評価テーブル"""

    __tablename__ = "odai_ratings"

    id = Column(Integer, primary_key=True, index=True)
    odai_text = Column(Text, nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5の評価
    source = Column(String(100))  # どの生成方法で作られたか
    feedback = Column(Text)  # フィードバックコメント
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<OdaiRating(id={self.id}, text='{self.odai_text[:30]}...', rating={self.rating})>"
