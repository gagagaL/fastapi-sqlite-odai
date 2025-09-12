from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict

from app.database.database import get_db
from app.models.news_article import NewsArticle
from app.scraping.news_scraper import collect_all_news, scrape_article
from app.scraping.mecab_word_extractor import MeCabWordExtractor

router = APIRouter(
    prefix="/api/scraping",
    tags=["scraping"]
)

@router.post("/full-pipeline-mecab")
async def run_mecab_pipeline(
    articles_per_site: int = 2,
    db: Session = Depends(get_db)
):
    """MeCabを使用した完全パイプライン"""
    try:
        # 1. ニュース記事収集
        news_results = await collect_all_news(articles_per_site)
        
        # 2. MeCab初期化
        extractor = MeCabWordExtractor()
        
        # 3. 収集した記事から単語抽出
        word_results = []
        for article in news_results.get("articles", []):
            extracted = extractor.extract_words_mecab(article.content)
            if "error" not in extracted:
                word_results.append(extracted)
        
        return {
            "message": "MeCabパイプライン完了",
            "news_collection": news_results,
            "word_extraction": {
                "processed": len(word_results),
                "words": word_results
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MeCabパイプラインエラー: {str(e)}")

@router.get("/mecab-status")
async def check_mecab_status():
    """MeCabの状態確認"""
    try:
        extractor = MeCabWordExtractor()
        is_available = extractor.is_mecab_available()
        
        test_text = "これはテスト文章です。MeCabの動作を確認します。"
        test_result = extractor.extract_words_mecab(test_text) if is_available else None
        
        return {
            "status": "available" if is_available else "unavailable",
            "test_extraction": test_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MeCab状態確認エラー: {str(e)}")

@router.post("/full-pipeline-enhanced")
async def run_enhanced_pipeline(
    articles_per_site: int = 2,
    db: Session = Depends(get_db)
):
    """拡張版（9サイト）完全パイプライン"""
    try:
        # 実装予定：9サイトからのスクレイピング
        return {"message": "拡張パイプライン完了"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拡張版パイプラインエラー: {str(e)}")