from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database.connection import get_db, init_db
from .database.crud import NewsArticleCRUD, ExtractedWordCRUD, OgiriTopicCRUD, TrainingTopicCRUD
from .database.models import NewsArticle as NewsArticleModel, ExtractedWord, OgiriTopic, TrainingTopic
from .config import get_settings
from .scraping import YahooNewsScraper, NHKNewsScraper, TextProcessor, SimpleWordExtractor
import os

# 設定読み込み
settings = get_settings()

# FastAPIアプリケーション初期化
app = FastAPI(
    title=settings.app_name,
    description="ニュースから単語を抽出して大喜利のお題を自動生成",
    version="1.0.0"
)

# 静的ファイルとテンプレートの設定
os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True) 
os.makedirs("app/templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    await init_db()
    print(f"🚀 {settings.app_name} が起動しました！")
    print(f"📖 API仕様: http://localhost:8000/docs")

# ============================================
# Web画面のルート
# ============================================

@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    """トップページ"""
    # 統計情報を取得（エラー回避版）
    try:
        stats = {
            "news_count": NewsArticleCRUD.get_count(db),
            "word_count": db.query(ExtractedWord).count(),
            "topic_count": db.query(OgiriTopic).count(),
            "training_count": db.query(TrainingTopic).count()
        }
    except Exception as e:
        print(f"統計取得エラー: {e}")
        stats = {
            "news_count": 0,
            "word_count": 0,
            "topic_count": 0,
            "training_count": 0
        }
    
    # 最新のお題をいくつか取得
    try:
        recent_topics = OgiriTopicCRUD.get_all(db, limit=5)
    except Exception as e:
        print(f"お題取得エラー: {e}")
        recent_topics = []
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "title": settings.app_name,
            "stats": stats,
            "recent_topics": recent_topics
        }
    )

@app.get("/topic")
async def show_random_topic(request: Request, db: Session = Depends(get_db)):
    """ランダムお題表示ページ"""
    try:
        topic = OgiriTopicCRUD.get_random(db)
    except:
        topic = None
    
    if not topic:
        # お題がない場合はサンプルお題を作成
        sample_topics = [
            "こんな時に限って必ず起こる、スマホの電池切れあるある",
            "宇宙人が地球に来て一番驚いたこと", 
            "AIが進化しすぎて困ること"
        ]
        try:
            for sample in sample_topics:
                OgiriTopicCRUD.create(db, sample)
            topic = OgiriTopicCRUD.get_random(db)
        except Exception as e:
            print(f"サンプルお題作成エラー: {e}")
    
    return templates.TemplateResponse(
        "topic.html",
        {
            "request": request,
            "title": "お題表示", 
            "topic": topic
        }
    )

@app.get("/admin")
async def admin_page(request: Request):
    """管理画面（基本版）"""
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "title": "管理画面"}
    )

# ============================================
# API ルート（基本版）
# ============================================

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """統計情報API"""
    try:
        return {
            "news_articles": NewsArticleCRUD.get_count(db),
            "extracted_words": db.query(ExtractedWord).count(),
            "ogiri_topics": len(OgiriTopicCRUD.get_all(db)) if hasattr(OgiriTopicCRUD, 'get_all') else 0,
            "training_topics": len(TrainingTopicCRUD.get_all(db)) if hasattr(TrainingTopicCRUD, 'get_all') else 0
        }
    except Exception as e:
        print(f"統計取得エラー: {e}")
        return {"error": str(e)}

@app.get("/api/topics/random")
async def get_random_topic(db: Session = Depends(get_db)):
    """ランダムお題取得API"""
    try:
        topic = OgiriTopicCRUD.get_random(db)
        if not topic:
            raise HTTPException(status_code=404, detail="お題が見つかりません")
        
        return {
            "id": topic.id,
            "topic_text": topic.topic_text,
            "is_generated": topic.is_generated,
            "created_at": topic.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"ランダムお題取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/topics")
async def create_topic(topic_text: str, db: Session = Depends(get_db)):
    """お題作成API"""
    if not topic_text.strip():
        raise HTTPException(status_code=400, detail="お題テキストが空です")
    
    try:
        topic = OgiriTopicCRUD.create(db, topic_text.strip())
        return {
            "id": topic.id,
            "topic_text": topic.topic_text,
            "message": "お題を作成しました"
        }
    except Exception as e:
        print(f"お題作成エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# テスト用のデータ投入API
# ============================================

@app.post("/api/admin/init-sample-data")
async def init_sample_data(db: Session = Depends(get_db)):
    """サンプルデータ初期投入"""
    
    try:
        # サンプルニュース記事
        sample_articles = [
            ("AIの進歩により新しい職業が誕生", "人工知能の発達に伴い、AIエンジニアやデータサイエンティストなどの新しい職業が注目されています。", "https://example.com/ai-news", "テックニュース"),
            ("宇宙探査の新発見", "火星で新しい鉱物が発見され、生命の痕跡の可能性が示唆されています。", "https://example.com/space-news", "科学ニュース"),
            ("スマートフォン新機能", "最新のスマートフォンには革新的なカメラ機能が搭載されています。", "https://example.com/phone-news", "ガジェットニュース")
        ]
        
        for title, content, url, source in sample_articles:
            NewsArticleCRUD.create(db, title, content, url, source)
        
        # サンプル単語
        sample_words = [
            ("AI", "名詞"), ("人工知能", "名詞"), ("スマートフォン", "名詞"),
            ("火星", "固有名詞"), ("カメラ", "名詞"), ("データ", "名詞")
        ]
        
        for word, word_type in sample_words:
            ExtractedWordCRUD.create_or_increment(db, word, word_type)
        
        # サンプル大喜利お題
        sample_topics = [
            "AIが進化しすぎて困ること",
            "火星に住んだら起こりそうな問題", 
            "スマホのカメラがさらに進化したらこうなる",
            "未来の職業あるある",
            "宇宙人が地球に来て驚くこと"
        ]
        
        for topic in sample_topics:
            OgiriTopicCRUD.create(db, topic, is_generated=False)
        
        # 学習用お題サンプル
        training_topics = [
            "こんな○○は嫌だ",
            "○○あるある", 
            "○○が進化するとこうなる",
            "未来の○○",
            "もしも○○だったら"
        ]
        
        TrainingTopicCRUD.bulk_create(db, training_topics)
        
        return {"message": "サンプルデータを投入しました！"}
        
    except Exception as e:
        print(f"サンプルデータ投入エラー: {e}")
        return {"message": f"エラーが発生しましたが一部は投入されました: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

@app.post("/api/scraping/collect-news")
async def collect_news(
    source: str = "yahoo",  # yahoo or nhk
    max_articles: int = 5,
    db: Session = Depends(get_db)
):
    """ニュース記事を収集"""
    
    if max_articles > 20:
        raise HTTPException(status_code=400, detail="一度に取得できる記事数は20件までです")
    
    try:
        # スクレイパー選択
        if source.lower() == "yahoo":
            scraper = YahooNewsScraper()
        elif source.lower() == "nhk":
            scraper = NHKNewsScraper()
        else:
            raise HTTPException(status_code=400, detail="サポートされていないニュースソースです")
        
        # 記事収集
        articles = scraper.scrape_articles(max_articles)
        
        if not articles:
            return {"message": "記事が取得できませんでした", "count": 0}
        
        # データベースに保存
        saved_count = 0
        for article in articles:
            try:
                # 既存チェック（URLで重複回避）
                existing = db.query(NewsArticleModel).filter(NewsArticleModel.url == article.url).first()
                if not existing:
                    NewsArticleCRUD.create(
                        db, 
                        title=article.title,
                        content=article.content,
                        url=article.url,
                        source=article.source
                    )
                    saved_count += 1
                else:
                    print(f"記事は既に存在します: {article.url}")
            except Exception as e:
                print(f"記事保存エラー: {e}")
                continue
        
        return {
            "message": f"{source}ニュースから{saved_count}件の新しい記事を収集しました",
            "source": source,
            "collected": len(articles),
            "saved": saved_count,
            "articles": [{"title": a.title, "url": a.url} for a in articles[:3]]  # 最初の3件のタイトル
        }
        
    except Exception as e:
        print(f"ニュース収集エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ニュース収集エラー: {str(e)}")

@app.post("/api/scraping/extract-words")
async def extract_words_from_articles(
    max_articles: int = 10,
    db: Session = Depends(get_db)
):
    """記事から単語を抽出"""
    
    try:
        # 最新の記事を取得
        articles = NewsArticleCRUD.get_all(db, limit=max_articles)
        
        if not articles:
            raise HTTPException(status_code=404, detail="記事が見つかりません")
        
        # テキスト処理と単語抽出
        processor = TextProcessor()
        extractor = SimpleWordExtractor()
        
        extracted_count = 0
        all_words = []
        processed_articles = 0
        
        for article in articles:
            try:
                # テキスト前処理
                clean_title = processor.clean_text(article.title)
                clean_content = processor.clean_text(article.content)
                combined_text = f"{clean_title} {clean_content}"
                
                # 単語抽出
                extracted = extractor.extract_words(combined_text)
                
                # データベースに保存
                for category, words in extracted.items():
                    for word in words:
                        if len(word) >= 2:  # 2文字以上の単語のみ
                            ExtractedWordCRUD.create_or_increment(
                                db,
                                word=word,
                                word_type=category,
                                source_article_id=article.id
                            )
                            all_words.append(word)
                            extracted_count += 1
                
                processed_articles += 1
                
            except Exception as e:
                print(f"記事処理エラー (ID: {article.id}): {e}")
                continue
        
        # 頻出単語統計
        frequent_words = extractor.get_frequent_words([" ".join(all_words)]) if all_words else {}
        
        return {
            "message": f"{processed_articles}件の記事から{extracted_count}個の単語を抽出しました",
            "processed_articles": processed_articles,
            "extracted_words": extracted_count,
            "top_words": dict(list(frequent_words.items())[:10]),
            "word_categories": {
                "proper_nouns": len([w for w in all_words if len(w) >= 2]),
                "common_nouns": len([w for w in all_words if len(w) >= 2]),
                "keywords": len([w for w in all_words if len(w) >= 2])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"単語抽出エラー: {e}")
        raise HTTPException(status_code=500, detail=f"単語抽出エラー: {str(e)}")

@app.post("/api/scraping/full-pipeline")  
async def run_full_scraping_pipeline(
    source: str = "yahoo",
    max_articles: int = 5,
    db: Session = Depends(get_db)
):
    """完全なスクレイピングパイプライン（収集→単語抽出）"""
    
    try:
        # Step 1: ニュース収集
        collect_result = await collect_news(source, max_articles, db)
        
        if collect_result["saved"] == 0:
            return {
                "message": "新しい記事がありませんでした（既存記事のみ）",
                "news_collection": collect_result,
                "word_extraction": {"extracted_words": 0}
            }
        
        # Step 2: 単語抽出（新しい記事のみ）
        extract_result = await extract_words_from_articles(collect_result["saved"], db)
        
        return {
            "message": "スクレイピングパイプライン完了",
            "news_collection": collect_result,
            "word_extraction": extract_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"パイプラインエラー: {e}")
        raise HTTPException(status_code=500, detail=f"パイプラインエラー: {str(e)}")

@app.get("/api/scraping/stats")
async def get_scraping_stats(db: Session = Depends(get_db)):
    """スクレイピング統計情報"""
    
    try:
        # 基本統計
        total_articles = NewsArticleCRUD.get_count(db)
        total_words = db.query(ExtractedWord).count()
        
        # ソース別統計
        source_stats = {}
        try:
            sources = db.query(NewsArticleModel.source, func.count(NewsArticleModel.id)).group_by(NewsArticleModel.source).all()
            for source, count in sources:
                source_stats[source or "不明"] = count
        except Exception as e:
            print(f"ソース統計エラー: {e}")
            source_stats = {"エラー": "統計取得失敗"}
        
        # 頻出単語トップ10
        word_stats = []
        try:
            top_words = ExtractedWordCRUD.get_frequent_words(db, 10)
            word_stats = [{"word": w.word, "frequency": w.frequency, "type": w.word_type} for w in top_words]
        except Exception as e:
            print(f"単語統計エラー: {e}")
        
        # 最新記事
        recent_stats = []
        try:
            recent_articles = NewsArticleCRUD.get_all(db, limit=5)
            recent_stats = [
                {
                    "title": article.title[:50] + "..." if len(article.title) > 50 else article.title,
                    "source": article.source,
                    "created_at": article.created_at.strftime("%Y-%m-%d %H:%M")
                } 
                for article in recent_articles
            ]
        except Exception as e:
            print(f"最新記事統計エラー: {e}")
        
        return {
            "total_articles": total_articles,
            "total_words": total_words,
            "source_distribution": source_stats,
            "top_words": word_stats,
            "recent_articles": recent_stats
        }
        
    except Exception as e:
        print(f"統計取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"統計取得エラー: {str(e)}")