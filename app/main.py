from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .database.connection import get_db, init_db
from .database.crud import NewsArticleCRUD, ExtractedWordCRUD, OgiriTopicCRUD, TrainingTopicCRUD
from .config import get_settings
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
    # 統計情報を取得
    stats = {
        "news_count": NewsArticleCRUD.get_count(db),
        "word_count": db.query(ExtractedWord).count(),
        "topic_count": db.query(OgiriTopic).count(),
        "training_count": db.query(TrainingTopic).count()
    }
    
    # 最新のお題をいくつか取得
    recent_topics = OgiriTopicCRUD.get_all(db, limit=5)
    
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
    topic = OgiriTopicCRUD.get_random(db)
    
    if not topic:
        # お題がない場合はサンプルお題を作成
        sample_topics = [
            "こんな時に限って必ず起こる、スマホの電池切れあるある",
            "宇宙人が地球に来て一番驚いたこと",
            "AIが進化しすぎて困ること"
        ]
        for sample in sample_topics:
            OgiriTopicCRUD.create(db, sample)
        
        topic = OgiriTopicCRUD.get_random(db)
    
    return templates.TemplateResponse(
        "topic.html",
        {
            "request": request,
            "title": "お題表示",
            "topic": topic
        }
    )

# ============================================
# API ルート
# ============================================

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """統計情報API"""
    return {
        "news_articles": NewsArticleCRUD.get_count(db),
        "extracted_words": db.query(ExtractedWord).count(),
        "ogiri_topics": db.query(OgiriTopic).count(),
        "training_topics": db.query(TrainingTopic).count()
    }

@app.get("/api/topics/random")
async def get_random_topic(db: Session = Depends(get_db)):
    """ランダムお題取得API"""
    topic = OgiriTopicCRUD.get_random(db)
    if not topic:
        raise HTTPException(status_code=404, detail="お題が見つかりません")
    
    return {
        "id": topic.id,
        "topic_text": topic.topic_text,
        "is_generated": topic.is_generated,
        "created_at": topic.created_at
    }

@app.post("/api/topics")
async def create_topic(topic_text: str, db: Session = Depends(get_db)):
    """お題作成API"""
    if not topic_text.strip():
        raise HTTPException(status_code=400, detail="お題テキストが空です")
    
    topic = OgiriTopicCRUD.create(db, topic_text.strip())
    return {
        "id": topic.id,
        "topic_text": topic.topic_text,
        "message": "お題を作成しました"
    }

@app.get("/api/words/frequent")
async def get_frequent_words(limit: int = 20, db: Session = Depends(get_db)):
    """頻出単語取得API"""
    words = ExtractedWordCRUD.get_frequent_words(db, limit)
    return [
        {
            "word": w.word,
            "word_type": w.word_type,
            "frequency": w.frequency
        } for w in words
    ]

# ============================================
# テスト用のデータ投入API
# ============================================

@app.post("/api/admin/init-sample-data")
async def init_sample_data(db: Session = Depends(get_db)):
    """サンプルデータ初期投入"""
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)