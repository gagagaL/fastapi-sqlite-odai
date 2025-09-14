from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.extracted_word import ExtractedWord
from app.models.news_article import NewsArticle
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/words",
    tags=["words"]
)

@router.get("/list")
async def list_words(
    page: int = Query(1, gt=0),
    per_page: int = Query(20, gt=0),
    db: Session = Depends(get_db)
):
    """抽出された単語一覧を取得"""
    try:
        # 単語一覧を取得（記事情報も含む）
        words = db.query(ExtractedWord)\
            .join(NewsArticle)\
            .order_by(ExtractedWord.importance_score.desc(), ExtractedWord.frequency.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": word.id,
                    "word": word.word,
                    "frequency": word.frequency,
                    "importance_score": word.importance_score,
                    "part_of_speech": word.part_of_speech,
                    "context": word.context,
                    "article": {
                        "title": word.article.title,
                        "url": word.article.url,
                        "source": word.article.source
                    } if word.article else None
                }
                for word in words
            ]
        }
    except Exception as e:
        logger.error(f"単語リスト取得エラー: {e}")
        return {
            "status": "error",
            "message": str(e)
        }