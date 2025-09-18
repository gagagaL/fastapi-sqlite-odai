from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from .models import NewsArticle, ExtractedWord, OgiriTopic, TrainingTopic, DisplayWord
from typing import List, Optional
import json

class NewsArticleCRUD:
    @staticmethod
    def create(db: Session, title: str, content: str, url: str = None, source: str = None):
        """ニュース記事を作成"""
        article = NewsArticle(
            title=title,
            content=content,
            url=url,
            source=source
        )
        db.add(article)
        db.commit()
        db.refresh(article)
        return article
    
    @staticmethod
    def get_by_id(db: Session, article_id: int) -> Optional[NewsArticle]:
        """IDでニュース記事を取得"""
        return db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[NewsArticle]:
        """全ニュース記事を取得"""
        return db.query(NewsArticle).order_by(desc(NewsArticle.created_at)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_count(db: Session) -> int:
        """ニュース記事の総数を取得"""
        return db.query(NewsArticle).count()

class ExtractedWordCRUD:
    @staticmethod
    def create_or_increment(db: Session, word: str, word_type: str, source_article_id: int = None):
        """単語を作成、または存在する場合は頻度をインクリメント"""
        existing_word = db.query(ExtractedWord).filter(ExtractedWord.word == word).first()
        
        if existing_word:
            existing_word.frequency += 1
            db.commit()
            db.refresh(existing_word)
            return existing_word
        else:
            new_word = ExtractedWord(
                word=word,
                word_type=word_type,
                source_article_id=source_article_id
            )
            db.add(new_word)
            db.commit()
            db.refresh(new_word)
            return new_word
    
    @staticmethod
    def get_frequent_words(db: Session, limit: int = 50) -> List[ExtractedWord]:
        """頻度の高い単語を取得"""
        return db.query(ExtractedWord).order_by(desc(ExtractedWord.frequency)).limit(limit).all()
    
    @staticmethod
    def get_by_type(db: Session, word_type: str, limit: int = 100) -> List[ExtractedWord]:
        """単語タイプで絞り込んで取得"""
        return db.query(ExtractedWord).filter(ExtractedWord.word_type == word_type).order_by(desc(ExtractedWord.frequency)).limit(limit).all()

class OgiriTopicCRUD:
    @staticmethod
    def create(db: Session, topic_text: str, is_generated: bool = False, used_words: List[str] = None):
        """大喜利お題を作成"""
        used_words_json = json.dumps(used_words, ensure_ascii=False) if used_words else None
        
        topic = OgiriTopic(
            topic_text=topic_text,
            is_generated=is_generated,
            used_words=used_words_json
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return topic
    
    @staticmethod
    def get_random(db: Session) -> Optional[OgiriTopic]:
        """ランダムでお題を取得"""
        return db.query(OgiriTopic).order_by(func.random()).first()
    
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[OgiriTopic]:
        """全お題を取得"""
        return db.query(OgiriTopic).order_by(desc(OgiriTopic.created_at)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_generated_topics(db: Session, limit: int = 50) -> List[OgiriTopic]:
        """自動生成されたお題のみ取得"""
        return db.query(OgiriTopic).filter(OgiriTopic.is_generated == True).order_by(desc(OgiriTopic.created_at)).limit(limit).all()

class TrainingTopicCRUD:
    @staticmethod
    def create(db: Session, topic_text: str):
        """学習用お題を作成"""
        topic = TrainingTopic(topic_text=topic_text)
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return topic
    
    @staticmethod
    def get_all(db: Session) -> List[TrainingTopic]:
        """全学習用お題を取得"""
        return db.query(TrainingTopic).all()
    
    @staticmethod
    def bulk_create(db: Session, topic_texts: List[str]):
        """学習用お題を一括作成"""
        topics = [TrainingTopic(topic_text=text) for text in topic_texts]
        db.add_all(topics)
        db.commit()
        return topics

class DisplayWordCRUD:
    @staticmethod
    def create(db: Session, word: str, pos: str = None):
        """表示用単語を作成"""
        display_word = DisplayWord(word=word, pos=pos)
        db.add(display_word)
        db.commit()
        db.refresh(display_word)
        return display_word
    
    @staticmethod
    def get_all(db: Session) -> List[DisplayWord]:
        """全表示用単語を取得"""
        return db.query(DisplayWord).order_by(desc(DisplayWord.created_at)).all()
    
    @staticmethod
    def delete(db: Session, word_id: int) -> bool:
        """表示用単語を削除"""
        word = db.query(DisplayWord).filter(DisplayWord.id == word_id).first()
        if word:
            db.delete(word)
            db.commit()
            return True
        return False