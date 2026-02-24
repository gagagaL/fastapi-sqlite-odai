from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from .models import (
    DisplayWord,
    ConfirmedOdai,
    OdaiRating,
)
from typing import List, Optional


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

    @staticmethod
    def delete_all(db: Session) -> int:
        """全表示用単語を削除"""
        deleted_count = db.query(DisplayWord).count()
        db.query(DisplayWord).delete()
        db.commit()
        return deleted_count

    @staticmethod
    def get_by_pos(db: Session, pos: str) -> List[DisplayWord]:
        """指定された品詞の単語を取得"""
        return db.query(DisplayWord).filter(DisplayWord.pos == pos).all()

    @staticmethod
    def get_random_by_pos(db: Session, pos: str, limit: int = 10) -> List[DisplayWord]:
        """指定された品詞からランダムに単語を取得"""
        return (
            db.query(DisplayWord)
            .filter(DisplayWord.pos == pos)
            .order_by(func.random())
            .limit(limit)
            .all()
        )


class ConfirmedOdaiCRUD:
    @staticmethod
    def create(
        db: Session, odai_text: str, source: str = "manual", quality_score: float = 0.0
    ):
        """確定お題を作成"""
        confirmed_odai = ConfirmedOdai(
            odai_text=odai_text, source=source, quality_score=quality_score
        )
        db.add(confirmed_odai)
        db.commit()
        db.refresh(confirmed_odai)
        return confirmed_odai

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[ConfirmedOdai]:
        """全確定お題を取得"""
        return (
            db.query(ConfirmedOdai)
            .order_by(desc(ConfirmedOdai.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, odai_id: int) -> Optional[ConfirmedOdai]:
        """IDで確定お題を取得"""
        return db.query(ConfirmedOdai).filter(ConfirmedOdai.id == odai_id).first()

    @staticmethod
    def delete(db: Session, odai_id: int) -> bool:
        """確定お題を削除"""
        odai = db.query(ConfirmedOdai).filter(ConfirmedOdai.id == odai_id).first()
        if odai:
            db.delete(odai)
            db.commit()
            return True
        return False

    @staticmethod
    def delete_all(db: Session) -> int:
        """全確定お題を削除"""
        deleted_count = db.query(ConfirmedOdai).count()
        db.query(ConfirmedOdai).delete()
        db.commit()
        return deleted_count

    @staticmethod
    def get_count(db: Session) -> int:
        """確定お題の総数を取得"""
        return db.query(ConfirmedOdai).count()

    @staticmethod
    def set_active(db: Session, odai_id: int) -> bool:
        """指定されたお題を出題中に設定（他のお題は非出題中にする）"""
        db.query(ConfirmedOdai).update({"is_active": False})
        odai = db.query(ConfirmedOdai).filter(ConfirmedOdai.id == odai_id).first()
        if odai:
            odai.is_active = True
            db.commit()
            return True
        return False

    @staticmethod
    def get_active(db: Session) -> Optional[ConfirmedOdai]:
        """現在出題中のお題を取得"""
        return db.query(ConfirmedOdai).filter(ConfirmedOdai.is_active == True).first()

    @staticmethod
    def set_inactive(db: Session, odai_id: int) -> bool:
        """指定されたお題を非出題中にする"""
        odai = db.query(ConfirmedOdai).filter(ConfirmedOdai.id == odai_id).first()
        if odai:
            odai.is_active = False
            db.commit()
            return True
        return False


class OdaiRatingCRUD:
    @staticmethod
    def create(
        db: Session,
        odai_text: str,
        rating: int,
        source: str = None,
        feedback: str = None,
    ):
        """お題評価を作成"""
        rating_obj = OdaiRating(
            odai_text=odai_text, rating=rating, source=source, feedback=feedback
        )
        db.add(rating_obj)
        db.commit()
        db.refresh(rating_obj)
        return rating_obj

    @staticmethod
    def get_high_rated_odais(
        db: Session, min_rating: int = 4, limit: int = 100
    ) -> List[OdaiRating]:
        """高評価のお題を取得"""
        return (
            db.query(OdaiRating)
            .filter(OdaiRating.rating >= min_rating)
            .order_by(desc(OdaiRating.rating), desc(OdaiRating.created_at))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_ratings_by_source(db: Session, source: str) -> List[OdaiRating]:
        """ソース別の評価を取得"""
        return (
            db.query(OdaiRating)
            .filter(OdaiRating.source == source)
            .order_by(desc(OdaiRating.created_at))
            .all()
        )

    @staticmethod
    def get_average_rating_by_source(db: Session, source: str) -> float:
        """ソース別の平均評価を取得"""
        result = (
            db.query(func.avg(OdaiRating.rating))
            .filter(OdaiRating.source == source)
            .scalar()
        )
        return result if result else 0.0
