from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.extracted_word import ExtractedWord
from app.models.news_article import NewsArticle
from sqlalchemy import or_
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
    search: str = Query(None),
    db: Session = Depends(get_db)
):
    """抽出された単語一覧を取得（ページネーション・検索対応）"""
    try:
        # ベースクエリ
        query = db.query(ExtractedWord, NewsArticle)\
            .join(NewsArticle, ExtractedWord.source_article_id == NewsArticle.id)
        
        # 検索条件
        if search:
            query = query.filter(
                or_(
                    ExtractedWord.word.contains(search),
                    ExtractedWord.context.contains(search),
                    NewsArticle.title.contains(search)
                )
            )
        
        # 総数取得
        total_count = query.count()
        
        # ページネーション適用
        words_data = query\
            .order_by(ExtractedWord.importance_score.desc(), ExtractedWord.frequency.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        # レスポンス形式を統一
        words = []
        for word, article in words_data:
            words.append({
                "id": word.id,
                "word": word.word,
                "word_type": word.word_type,
                "frequency": word.frequency,
                "importance_score": round(word.importance_score or 0, 3),
                "context": word.context or "",
                "article_title": article.title,
                "article_url": article.url,
                "article_source": article.source,
                "created_at": word.created_at.strftime("%Y-%m-%d %H:%M") if word.created_at else ""
            })
        
        total_pages = (total_count + per_page - 1) // per_page
        
        return {
            "words": words,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "search": search
        }
        
    except Exception as e:
        logger.error(f"単語リスト取得エラー: {e}")
        return {
            "words": [],
            "page": 1,
            "per_page": per_page,
            "total_count": 0,
            "total_pages": 0,
            "search": search,
            "error": str(e)
        }
