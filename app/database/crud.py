from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from .models import NewsArticle, ExtractedWord, OgiriTopic, TrainingTopic
from typing import List, Optional, Dict  # Dict を追加
import json
from collections import defaultdict

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
    def create_or_increment_advanced(
        db: Session, 
        word: str, 
        word_type: str, 
        source_article_id: int = None,
        importance_score: float = 0.0,
        context: str = None
    ):
        """単語を作成、または存在する場合は頻度をインクリメント（拡張版）"""
        
        # 同じ記事からの同じ単語は1回のみカウント
        existing_word = db.query(ExtractedWord).filter(
            ExtractedWord.word == word,
            ExtractedWord.source_article_id == source_article_id
        ).first()
        
        if existing_word:
            # 既存の場合は重要度スコアを更新（最大値を採用）
            if hasattr(existing_word, 'importance_score'):
                existing_word.importance_score = max(
                    getattr(existing_word, 'importance_score', 0.0), 
                    importance_score
                )
            if context and not getattr(existing_word, 'context', None):
                existing_word.context = context[:500] if context else None
            db.commit()
            db.refresh(existing_word)
            return existing_word
        else:
            # 新規作成
            word_data = {
                'word': word,
                'word_type': word_type,
                'source_article_id': source_article_id
            }
            
            # 拡張フィールドがあれば追加
            if hasattr(ExtractedWord, 'importance_score'):
                word_data['importance_score'] = importance_score
            if hasattr(ExtractedWord, 'context'):
                word_data['context'] = context[:500] if context else None
                
            new_word = ExtractedWord(**word_data)
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
    
    @staticmethod
    def get_words_with_articles(db: Session, limit: int = 100) -> List[Dict]:
        """記事情報付きで単語を取得"""
        try:
            query = db.query(ExtractedWord, NewsArticle).join(
                NewsArticle, ExtractedWord.source_article_id == NewsArticle.id
            )
            
            # importance_scoreがあれば使用、なければfrequencyでソート
            if hasattr(ExtractedWord, 'importance_score'):
                query = query.order_by(
                    desc(ExtractedWord.importance_score),
                    desc(ExtractedWord.frequency)
                )
            else:
                query = query.order_by(desc(ExtractedWord.frequency))
            
            query = query.limit(limit)
            
            result = []
            for word, article in query:
                word_dict = {
                    "id": word.id,
                    "word": word.word,
                    "word_type": word.word_type,
                    "frequency": word.frequency,
                    "article_title": article.title,
                    "article_url": article.url,
                    "article_source": article.source,
                    "created_at": word.created_at
                }
                
                # 拡張フィールドがあれば追加
                if hasattr(word, 'importance_score'):
                    word_dict["importance_score"] = getattr(word, 'importance_score', 0.0)
                if hasattr(word, 'context'):
                    word_dict["context"] = getattr(word, 'context', None)
                
                result.append(word_dict)
            
            return result
            
        except Exception as e:
            print(f"get_words_with_articles エラー: {e}")
            return []
    
    @staticmethod
    def search_words(db: Session, query_text: str, limit: int = 50) -> List[Dict]:
        """単語を検索"""
        try:
            search_query = db.query(ExtractedWord, NewsArticle).join(
                NewsArticle, ExtractedWord.source_article_id == NewsArticle.id
            ).filter(
                ExtractedWord.word.contains(query_text)
            )
            
            # importance_scoreがあれば使用
            if hasattr(ExtractedWord, 'importance_score'):
                search_query = search_query.order_by(desc(ExtractedWord.importance_score))
            else:
                search_query = search_query.order_by(desc(ExtractedWord.frequency))
            
            search_query = search_query.limit(limit)
            
            result = []
            for word, article in search_query:
                word_dict = {
                    "word": word.word,
                    "word_type": word.word_type,
                    "frequency": word.frequency,
                    "article_title": article.title,
                    "article_url": article.url,
                    "article_source": article.source
                }
                
                # 拡張フィールドがあれば追加
                if hasattr(word, 'importance_score'):
                    word_dict["importance_score"] = getattr(word, 'importance_score', 0.0)
                if hasattr(word, 'context'):
                    word_dict["context"] = getattr(word, 'context', None)
                
                result.append(word_dict)
            
            return result
            
        except Exception as e:
            print(f"search_words エラー: {e}")
            return []

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