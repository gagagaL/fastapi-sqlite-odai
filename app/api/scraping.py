from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.orm import Session
import logging
from app.database.database import get_db
from app.scraping.news_scraper import collect_all_news
from app.scraping.word_extractor import MeCabWordExtractor
from app.database.crud import ExtractedWordCRUD, NewsArticleCRUD

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/scraping",
    tags=["scraping"]
)

@router.post("/full-pipeline-all")
async def run_full_pipeline(
    articles_per_site: int = Form(20),
    db: Session = Depends(get_db)
):
    """記事収集と単語抽出を実行（全サイト）"""
    try:
        logger.info(f"全サイトから各{articles_per_site}件の記事収集を開始...")
        results = await collect_all_news(articles_per_site, db)
        
        if results['saved'] == 0:
            return {
                "status": "success",
                "message": "新しい記事はありませんでした",
                "collected": results['collected'],
                "saved": 0,
                "words": 0
            }

        # 単語抽出
        extractor = MeCabWordExtractor()
        total_words = 0
        
        # 新規記事から単語を抽出
        articles = NewsArticleCRUD.get_all(db, limit=results['saved'])
        for article in articles:
            nouns = extractor.extract_nouns(article.content)
            for noun in nouns:
                ExtractedWordCRUD.create_or_update(db, {
                    'word': noun['word'],
                    'category': noun['category'],
                    'context': noun['context']
                }, article.id)
                total_words += 1

        return {
            "status": "success",
            "message": "パイプライン完了",
            "collected": results['collected'],
            "saved": results['saved'],
            "words": total_words,
            "sources": results['sources']
        }

    except Exception as e:
        logger.error(f"パイプラインエラー: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"パイプライン実行エラー: {str(e)}"
        )

@router.get("/stats")
async def get_scraping_stats(db: Session = Depends(get_db)):
    """スクレイピング状況を取得"""
    try:
        articles = NewsArticleCRUD.get_stats(db)
        words = ExtractedWordCRUD.get_stats(db)
        
        return {
            "articles": articles,
            "words": words,
            "status": "healthy" if articles['total'] > 0 else "empty"
        }
    except Exception as e:
        logger.error(f"統計取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"統計取得エラー: {str(e)}"
        )