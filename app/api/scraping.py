from fastapi import APIRouter, HTTPException, Depends, Form, Query
from sqlalchemy.orm import Session
import logging
from app.database.database import get_db
from app.scraping.news_scraper import collect_all_news
from app.scraping.multi_site_scraper import EnhancedMultiSiteScraper
from app.scraping.word_extractor import MeCabWordExtractor
from app.database.crud import ExtractedWordCRUD, NewsArticleCRUD
from app.models.extracted_word import ExtractedWord

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/scraping",
    tags=["scraping"]
)

@router.post("/full-pipeline-all")
async def run_full_pipeline(
    articles_per_site: int = Form(2),
    db: Session = Depends(get_db)
):
    """記事収集と単語抽出を実行（全サイト・全カテゴリ）"""
    try:
        logger.info(f"全サイト・全カテゴリから各{articles_per_site}件の記事収集を開始...")
        
        # 全カテゴリから記事を収集
        scraper = EnhancedMultiSiteScraper()
        all_categories_results = scraper.scrape_all_categories(articles_per_site)
        
        total_collected = 0
        total_saved = 0
        all_sources = {}
        
        # 各カテゴリの記事を保存
        for category, articles in all_categories_results.items():
            logger.info(f"=== {category}カテゴリ: {len(articles)}件の記事を処理中 ===")
            category_saved = 0
            
            for article in articles:
                try:
                    # 記事の重複チェックと保存
                    article_data = {
                        'title': article.title,
                        'content': article.content,
                        'url': article.url,
                        'source': article.source
                    }
                    
                    saved_article = NewsArticleCRUD.create_if_not_exists(db, article_data)
                    if saved_article:
                        category_saved += 1
                        total_saved += 1
                        
                        # 単語抽出
                        extractor = MeCabWordExtractor()
                        nouns = extractor.extract_nouns(saved_article.content)
                        for noun in nouns:
                            ExtractedWordCRUD.create_or_update_global(db, {
                                'word': noun['word'],
                                'category': noun['category'],
                                'context': noun['context']
                            }, saved_article.id)
                    
                    # ソース別集計
                    source = article.source
                    all_sources[source] = all_sources.get(source, 0) + 1
                    total_collected += 1
                    
                except Exception as e:
                    logger.warning(f"記事保存エラー: {e}")
                    continue
            
            logger.info(f"{category}カテゴリ: {category_saved}件保存完了")
        
        # 単語数をカウント
        total_words = db.query(ExtractedWord).count()
        
        logger.info(f"=== 全カテゴリ収集完了: {total_collected}件収集, {total_saved}件保存 ===")
        logger.info("=== ソース別統計 ===")
        for source, count in all_sources.items():
            logger.info(f"{source}: {count}件")

        return {
            "status": "success",
            "message": "全カテゴリ収集完了",
            "collected": total_collected,
            "saved": total_saved,
            "words": total_words,
            "sources": all_sources,
            "categories": {cat: len(articles) for cat, articles in all_categories_results.items()}
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
        
        # お題数と学習データ数を取得
        from app.models.topic import OgiriTopic, TrainingTopic
        ogiri_count = db.query(OgiriTopic).count()
        training_count = db.query(TrainingTopic).count()
        
        return {
            "articles": articles,
            "words": words,
            "ogiri_topics": ogiri_count,
            "training_topics": training_count,
            "status": "healthy" if articles['total'] > 0 else "empty"
        }
    except Exception as e:
        logger.error(f"統計取得エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"統計取得エラー: {str(e)}"
        )