from sqlalchemy import func, desc, inspect
from sqlalchemy.orm import Session
from app.models.news_article import NewsArticle
from app.models.extracted_word import ExtractedWord
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from app.models.topic import OgiriTopic, TrainingTopic

class NewsArticleCRUD:
    @staticmethod
    def get_count(db: Session) -> int:
        return db.query(NewsArticle).count()

    @staticmethod
    def get_all(db: Session, limit: int = None) -> List[NewsArticle]:
        query = db.query(NewsArticle).order_by(desc(NewsArticle.created_at))
        if limit:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def get_by_id(db: Session, article_id: int) -> Optional[NewsArticle]:
        return db.query(NewsArticle).filter(NewsArticle.id == article_id).first()

    @staticmethod
    def create(db: Session, title: str, content: str, url: str, source: str) -> NewsArticle:
        db_article = NewsArticle(
            title=title,
            content=content,
            url=url,
            source=source
        )
        db.add(db_article)
        db.commit()
        db.refresh(db_article)
        return db_article

    @staticmethod
    def get_stats(db: Session) -> Dict:
        """記事の統計情報を取得"""
        total = db.query(NewsArticle).count()
        sources = db.query(
            NewsArticle.source,
            func.count(NewsArticle.id)
        ).group_by(NewsArticle.source).all()
        
        return {
            "total": total,
            "sources": dict(sources)
        }

class ExtractedWordCRUD:
    @staticmethod
    def create_or_update(db: Session, word_data: Dict, article_id: int) -> ExtractedWord:
        """単語を作成または更新"""
        word = word_data['word']
        existing = db.query(ExtractedWord).filter(
            ExtractedWord.word == word,
            ExtractedWord.source_article_id == article_id
        ).first()
        
        if existing:
            existing.frequency += 1
            db.commit()
            return existing
            
        new_word = ExtractedWord(
            word=word,
            word_type=word_data.get('category', '一般'),
            context=word_data.get('context', ''),
            source_article_id=article_id,
            frequency=1
        )
        
        db.add(new_word)
        db.commit()
        return new_word

    @staticmethod
    def get_all(db: Session, limit: int = None) -> List[ExtractedWord]:
        query = db.query(ExtractedWord).order_by(
            desc(ExtractedWord.importance_score),
            desc(ExtractedWord.frequency)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def create(db: Session, word_data: Dict) -> ExtractedWord:
        db_word = ExtractedWord(**word_data)
        db.add(db_word)
        db.commit()
        db.refresh(db_word)
        return db_word

    @staticmethod
    def get_or_create(db: Session, word: str, article_id: int) -> ExtractedWord:
        db_word = db.query(ExtractedWord).filter(
            ExtractedWord.word == word,
            ExtractedWord.source_article_id == article_id
        ).first()
        
        if not db_word:
            db_word = ExtractedWord(
                word=word,
                source_article_id=article_id,
                frequency=1
            )
            db.add(db_word)
            db.commit()
            db.refresh(db_word)
        
        return db_word

    @staticmethod
    def get_stats(db: Session) -> Dict:
        """単語の統計情報を取得"""
        return {
            "total": db.query(ExtractedWord).count(),
            "unique": db.query(func.count(func.distinct(ExtractedWord.word))).scalar()
        }

class OgiriTopicCRUD:
    @staticmethod
    def create(db: Session, title: str, content: str) -> OgiriTopic:
        db_topic = OgiriTopic(
            title=title,
            content=content,
            is_active=True
        )
        db.add(db_topic)
        db.commit()
        db.refresh(db_topic)
        return db_topic

    @staticmethod
    def get_random(db: Session) -> Optional[OgiriTopic]:
        return db.query(OgiriTopic)\
            .filter(OgiriTopic.is_active == True)\
            .order_by(func.random())\
            .first()

    @staticmethod
    def get_all(db: Session, active_only: bool = False) -> List[OgiriTopic]:
        query = db.query(OgiriTopic)
        if active_only:
            query = query.filter(OgiriTopic.is_active == True)
        return query.order_by(desc(OgiriTopic.created_at)).all()

class TrainingTopicCRUD:
    @staticmethod
    def create(db: Session, title: str, content: str, category: str) -> TrainingTopic:
        db_topic = TrainingTopic(
            title=title,
            content=content,
            category=category
        )
        db.add(db_topic)
        db.commit()
        db.refresh(db_topic)
        return db_topic

    @staticmethod
    def get_random(db: Session, category: Optional[str] = None) -> Optional[TrainingTopic]:
        query = db.query(TrainingTopic)
        if category:
            query = query.filter(TrainingTopic.category == category)
        return query.order_by(func.random()).first()

    @staticmethod
    def get_all(db: Session) -> List[TrainingTopic]:
        return db.query(TrainingTopic)\
            .order_by(desc(TrainingTopic.created_at))\
            .all()

class DatabaseStatusCRUD:
    @staticmethod
    def check_database_status(db: Session) -> Tuple[str, Dict]:
        """データベースの状態を確認する"""
        try:
            tables_status = {}
            overall_status = "healthy"

            # 必要なテーブルと対応するモデルのマッピング
            required_tables = {
                'news_articles': NewsArticle,
                'extracted_words': ExtractedWord,
                'ogiri_topics': OgiriTopic,
                'training_topics': TrainingTopic
            }

            # テーブルの存在確認とレコード数取得
            inspector = inspect(db.bind)
            existing_tables = inspector.get_table_names()

            for table_name, model in required_tables.items():
                if table_name not in existing_tables:
                    tables_status[table_name] = {
                        "exists": False,
                        "count": 0,
                        "status": "❌ テーブル不存在"
                    }
                    overall_status = "needs_repair"
                else:
                    try:
                        count = db.query(model).count()
                        tables_status[table_name] = {
                            "exists": True,
                            "count": count,
                            "status": "✅ 正常"
                        }
                    except Exception as e:
                        tables_status[table_name] = {
                            "exists": True,
                            "count": 0,
                            "status": f"❌ エラー: {str(e)}"
                        }
                        overall_status = "error"

            return overall_status, tables_status

        except Exception as e:
            return "error", {"error": str(e)}

    @staticmethod
    def repair_database(db: Session) -> Tuple[str, Dict]:
        """データベースを修復（テーブルを作成）する"""
        try:
            from app.database.database import Base, engine
            
            # 全テーブルを作成
            Base.metadata.create_all(bind=engine)
            
            # 作成後の状態を確認
            status, details = DatabaseStatusCRUD.check_database_status(db)
            
            return "success", {
                "message": "データベースを修復しました",
                "status": status,
                "details": details
            }
        except Exception as e:
            return "error", {
                "message": f"データベース修復エラー: {str(e)}"
            }