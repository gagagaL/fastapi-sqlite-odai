from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database.connection import get_db, init_db
from .database.crud import (
    NewsArticleCRUD,
    ExtractedWordCRUD,
    OgiriTopicCRUD,
    TrainingTopicCRUD,
    DisplayWordCRUD,
    ConfirmedOdaiCRUD,
)
from .database.models import (
    NewsArticle as NewsArticleModel,
    ExtractedWord,
    OgiriTopic,
    TrainingTopic,
    DisplayWord,
    ConfirmedOdai,
)
from .config import get_settings
from .scraping import YahooNewsScraper, NHKNewsScraper, MeCabWordExtractor
import os
import re
import MeCab
import json, random, os
from fastapi import UploadFile, File
from sqlalchemy import text
from collections import defaultdict


MARKOV_PATH = "app/data/markov_model.json"
os.makedirs("app/data", exist_ok=True)


class MarkovModel:
    def __init__(self):
        self.chain = {}  # (c1,c2) -> [c3,...]

    def train_lines(self, lines: list[str]):
        for line in lines:
            text = (line or "").strip()
            if not text:
                continue
            s = f"^{text}$"  # 開始・終了マーカー
            for i in range(len(s) - 2):
                key = (s[i], s[i + 1])
                nxt = s[i + 2]
                self.chain.setdefault(key, []).append(nxt)

    def generate(self, seed_chars: str | None = None, max_len: int = 60) -> str:
        if not self.chain:
            return ""
        # 開始
        if seed_chars and len(seed_chars) >= 2:
            key = (seed_chars[0], seed_chars[1])
            if key not in self.chain:
                key = random.choice(list(self.chain.keys()))
        else:
            key = random.choice(list(self.chain.keys()))
        out = [key[0], key[1]]
        for _ in range(max_len):
            nxts = self.chain.get(key)
            if not nxts:
                break
            nxt = random.choice(nxts)
            out.append(nxt)
            if nxt == "$":
                break
            key = (key[1], nxt)
        s = "".join(out)
        return s.strip("^$")

    def dump(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"/".join(k): v for k, v in self.chain.items()}, f, ensure_ascii=False
            )

    def load(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.chain = {}
        for k, v in data.items():
            c1, c2 = k.split("/")
            self.chain[(c1, c2)] = v


markov = MarkovModel()
markov.load(MARKOV_PATH)

# 設定読み込み
settings = get_settings()

# FastAPIアプリケーション初期化
app = FastAPI(
    title=settings.app_name,
    description="ニュースから単語を抽出して大喜利のお題を自動生成",
    version="1.0.0",
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
    init_db()  # awaitを外す
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
            "training_count": db.query(TrainingTopic).count(),
        }
    except Exception as e:
        print(f"統計取得エラー: {e}")
        stats = {
            "news_count": 0,
            "word_count": 0,
            "topic_count": 0,
            "training_count": 0,
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
            "recent_topics": recent_topics,
        },
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
            "AIが進化しすぎて困ること",
        ]
        try:
            for sample in sample_topics:
                OgiriTopicCRUD.create(db, sample)
            topic = OgiriTopicCRUD.get_random(db)
        except Exception as e:
            print(f"サンプルお題作成エラー: {e}")

    return templates.TemplateResponse(
        "topic.html", {"request": request, "title": "お題表示", "topic": topic}
    )


@app.get("/admin")
async def admin_page(request: Request):
    """管理画面（基本版）"""
    return templates.TemplateResponse(
        "admin.html", {"request": request, "title": "管理画面"}
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
            "ogiri_topics": len(OgiriTopicCRUD.get_all(db))
            if hasattr(OgiriTopicCRUD, "get_all")
            else 0,
            "training_topics": len(TrainingTopicCRUD.get_all(db))
            if hasattr(TrainingTopicCRUD, "get_all")
            else 0,
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
            "created_at": topic.created_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"ランダムお題取得エラー: {e}")
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
            (
                "AIの進歩により新しい職業が誕生",
                "人工知能の発達に伴い、AIエンジニアやデータサイエンティストなどの新しい職業が注目されています。",
                "https://example.com/ai-news",
                "テックニュース",
            ),
            (
                "宇宙探査の新発見",
                "火星で新しい鉱物が発見され、生命の痕跡の可能性が示唆されています。",
                "https://example.com/space-news",
                "科学ニュース",
            ),
            (
                "スマートフォン新機能",
                "最新のスマートフォンには革新的なカメラ機能が搭載されています。",
                "https://example.com/phone-news",
                "ガジェットニュース",
            ),
        ]

        for title, content, url, source in sample_articles:
            NewsArticleCRUD.create(db, title, content, url, source)

        # サンプル単語
        sample_words = [
            ("AI", "名詞"),
            ("人工知能", "名詞"),
            ("スマートフォン", "名詞"),
            ("火星", "固有名詞"),
            ("カメラ", "名詞"),
            ("データ", "名詞"),
        ]

        for word, word_type in sample_words:
            ExtractedWordCRUD.create_or_increment(db, word, word_type)

        # サンプル大喜利お題
        sample_topics = [
            "AIが進化しすぎて困ること",
            "火星に住んだら起こりそうな問題",
            "スマホのカメラがさらに進化したらこうなる",
            "未来の職業あるある",
            "宇宙人が地球に来て驚くこと",
        ]

        for topic in sample_topics:
            OgiriTopicCRUD.create(db, topic, is_generated=False)

        # 学習用お題サンプルは削除（完全にゼロから学習）

        return {"message": "サンプルデータを投入しました！"}

    except Exception as e:
        print(f"サンプルデータ投入エラー: {e}")
        return {"message": f"エラーが発生しましたが一部は投入されました: {str(e)}"}


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
            "message": "お題を作成しました",
        }
    except Exception as e:
        print(f"お題作成エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


@app.post("/api/scraping/collect-news")
async def collect_news(
    source: str = "yahoo",  # yahoo or nhk
    max_articles: int = 5,
    db: Session = Depends(get_db),
):
    """ニュース記事を収集"""

    if max_articles > 20:
        raise HTTPException(
            status_code=400, detail="一度に取得できる記事数は20件までです"
        )

    try:
        # スクレイパー選択
        if source.lower() == "yahoo":
            scraper = YahooNewsScraper()
        elif source.lower() == "nhk":
            scraper = NHKNewsScraper()
        else:
            raise HTTPException(
                status_code=400, detail="サポートされていないニュースソースです"
            )

        # 記事収集
        articles = scraper.scrape_articles(max_articles)

        if not articles:
            return {"message": "記事が取得できませんでした", "count": 0}

        # データベースに保存
        saved_count = 0
        for article in articles:
            try:
                # 既存チェック（URLで重複回避）
                existing = (
                    db.query(NewsArticleModel)
                    .filter(NewsArticleModel.url == article.url)
                    .first()
                )
                if not existing:
                    NewsArticleCRUD.create(
                        db,
                        title=article.title,
                        content=article.content,
                        url=article.url,
                        source=article.source,
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
            "articles": [
                {"title": a.title, "url": a.url} for a in articles[:3]
            ],  # 最初の3件のタイトル
        }

    except Exception as e:
        print(f"ニュース収集エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ニュース収集エラー: {str(e)}")


@app.post("/api/scraping/extract-words")
async def extract_words_from_articles(
    max_articles: int = 10, db: Session = Depends(get_db)
):
    """記事から単語を抽出"""

    try:
        # 最新の記事を取得
        articles = NewsArticleCRUD.get_all(db, limit=max_articles)

        if not articles:
            raise HTTPException(status_code=404, detail="記事が見つかりません")

        # テキスト処理と単語抽出
        processor = TextProcessor()
        extractor = MeCabWordExtractor()

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
                                source_article_id=article.id,
                            )
                            all_words.append(word)
                            extracted_count += 1

                processed_articles += 1

            except Exception as e:
                print(f"記事処理エラー (ID: {article.id}): {e}")
                continue

        # 頻出単語統計
        frequent_words = (
            extractor.get_frequent_words([" ".join(all_words)]) if all_words else {}
        )

        return {
            "message": f"{processed_articles}件の記事から{extracted_count}個の単語を抽出しました",
            "processed_articles": processed_articles,
            "extracted_words": extracted_count,
            "top_words": dict(list(frequent_words.items())[:10]),
            "word_categories": {
                "proper_nouns": len([w for w in all_words if len(w) >= 2]),
                "common_nouns": len([w for w in all_words if len(w) >= 2]),
                "keywords": len([w for w in all_words if len(w) >= 2]),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"単語抽出エラー: {e}")
        raise HTTPException(status_code=500, detail=f"単語抽出エラー: {str(e)}")


@app.post("/api/scraping/full-pipeline")
async def run_full_scraping_pipeline(
    source: str = "yahoo", max_articles: int = 5, db: Session = Depends(get_db)
):
    """完全なスクレイピングパイプライン（収集→単語抽出）"""

    try:
        # Step 1: ニュース収集
        collect_result = await collect_news(source, max_articles, db)

        if collect_result["saved"] == 0:
            return {
                "message": "新しい記事がありませんでした（既存記事のみ）",
                "news_collection": collect_result,
                "word_extraction": {"extracted_words": 0},
            }

        # Step 2: 単語抽出（新しい記事のみ）
        extract_result = await extract_words_from_articles(collect_result["saved"], db)

        return {
            "message": "スクレイピングパイプライン完了",
            "news_collection": collect_result,
            "word_extraction": extract_result,
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
            sources = (
                db.query(NewsArticleModel.source, func.count(NewsArticleModel.id))
                .group_by(NewsArticleModel.source)
                .all()
            )
            for source, count in sources:
                source_stats[source or "不明"] = count
        except Exception as e:
            print(f"ソース統計エラー: {e}")
            source_stats = {"エラー": "統計取得失敗"}

        # 頻出単語トップ10
        word_stats = []
        try:
            top_words = ExtractedWordCRUD.get_frequent_words(db, 10)
            word_stats = [
                {"word": w.word, "frequency": w.frequency, "type": w.word_type}
                for w in top_words
            ]
        except Exception as e:
            print(f"単語統計エラー: {e}")

        # 最新記事
        recent_stats = []
        try:
            recent_articles = NewsArticleCRUD.get_all(db, limit=5)
            recent_stats = [
                {
                    "title": article.title[:50] + "..."
                    if len(article.title) > 50
                    else article.title,
                    "source": article.source,
                    "created_at": article.created_at.strftime("%Y-%m-%d %H:%M"),
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
            "recent_articles": recent_stats,
        }

    except Exception as e:
        print(f"統計取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"統計取得エラー: {str(e)}")


@app.get("/display")
async def display_page(request: Request, db: Session = Depends(get_db)):
    """単語表示ページ"""
    words_obj = DisplayWordCRUD.get_all(db)
    # オブジェクトをディクショナリに変換
    words = [
        {
            "id": w.id,
            "word": w.word,
            "pos": w.pos,
            "created_at": w.created_at.isoformat(),
        }
        for w in words_obj
    ]
    return templates.TemplateResponse(
        "display.html", {"request": request, "title": "単語表示", "words": words}
    )


# APIルートセクションに追加
@app.get("/api/display/words")
async def get_display_words(db: Session = Depends(get_db)):
    """表示用単語の一覧を取得"""
    words = DisplayWordCRUD.get_all(db)
    return {
        "words": [
            {
                "id": w.id,
                "word": w.word,
                "pos": w.pos,
                "created_at": w.created_at.isoformat(),
            }
            for w in words
        ]
    }


@app.post("/api/display/words")
async def create_display_word(
    word: str = Form(...), pos: str = Form(None), db: Session = Depends(get_db)
):
    """表示用単語を作成"""
    if not word.strip():
        raise HTTPException(status_code=400, detail="単語が空です")

    try:
        display_word = DisplayWordCRUD.create(db, word.strip(), pos)
        return {
            "id": display_word.id,
            "word": display_word.word,
            "pos": display_word.pos,
            "message": "単語を追加しました",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/display/words/{word_id}")
async def delete_display_word(word_id: int, db: Session = Depends(get_db)):
    """表示用単語を削除"""
    success = DisplayWordCRUD.delete(db, word_id)
    if not success:
        raise HTTPException(status_code=404, detail="指定された単語が見つかりません")

    return {"message": "単語を削除しました"}


@app.post("/api/display/sentence")
async def create_display_words_from_sentence(
    sentence: str = Form(...), db: Session = Depends(get_db)
):
    if not sentence.strip():
        raise HTTPException(status_code=400, detail="文章が空です")
    try:
        import re, MeCab

        tagger = MeCab.Tagger("")
        node = tagger.parseToNode(sentence)

        target_heads = {"名詞", "動詞", "形容詞", "形容動詞", "形容動詞語幹", "副詞"}
        allow_re = re.compile(
            r"^[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF10-\uFF19A-Za-z0-9ー\-]+$"
        )

        picked = []
        while node:
            surface = (node.surface or "").strip()  # ← 必ず元表記
            feat = node.feature or ""
            head = feat.split(",")[0] if feat else ""
            if head in target_heads and surface and allow_re.match(surface):
                exists = (
                    db.query(DisplayWord)
                    .filter(DisplayWord.word == surface, DisplayWord.pos == head)
                    .first()
                )
                if not exists:
                    DisplayWordCRUD.create(db, word=surface, pos=head)
                picked.append({"word": surface, "pos": head})
            node = node.next

        if not picked:
            raise HTTPException(
                status_code=400, detail="対象品詞が抽出されませんでした"
            )

        return {
            "nouns": [it["word"] for it in picked],
            "words": picked,
            "message": "品詞付きで抽出・追加しました",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 先頭付近（既存のMarkovModelの代わりに）に追加
import json, os, random
import MeCab

TOK_MARKOV_PATH = "app/data/markov_token_model.json"
LLM_LEARNED_DATA_PATH = "app/data/llm_learned_data.json"
os.makedirs("app/data", exist_ok=True)


class TokenMarkovModel:
    def __init__(self):
        self.chain = {}  # (t1, t2) -> [t3,...]
        self.tagger = MeCab.Tagger("")

    def tokenize(self, text: str) -> list[str]:
        node = self.tagger.parseToNode(text or "")
        toks = []
        while node:
            s = (node.surface or "").strip()
            if s:
                toks.append(s)
            node = node.next
        return toks

    def train_lines(self, lines: list[str]):
        for line in lines:
            toks = self.tokenize(line.strip())
            if not toks:
                continue
            # BOS/BOS で開始、EOS で終了（トークン連鎖）
            seq = ["<BOS>", "<BOS>"] + toks + ["<EOS>"]
            for i in range(len(seq) - 2):
                key = (seq[i], seq[i + 1])
                nxt = seq[i + 2]
                self.chain.setdefault(key, []).append(nxt)

    def generate(self, seed_tokens: list[str] | None = None, max_len: int = 60) -> str:
        if not self.chain:
            return ""
        # 開始
        if seed_tokens and len(seed_tokens) >= 2:
            key = (seed_tokens[0], seed_tokens[1])
            if key not in self.chain:
                key = random.choice(list(self.chain.keys()))
        else:
            key = random.choice(list(self.chain.keys()))
        out = [key[0], key[1]]
        for _ in range(max_len):
            nxts = self.chain.get(key)
            if not nxts:
                break
            nxt = random.choice(nxts)
            out.append(nxt)
            if nxt == "$":
                break
            key = (key[1], nxt)
        s = "".join(out)
        return s.strip("^$")

    def dump(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"\t".join(k): v for k, v in self.chain.items()}, f, ensure_ascii=False
            )

    def load(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.chain = {}
        for k, v in data.items():
            t1, t2 = k.split("\t")
            self.chain[(t1, t2)] = v


token_markov = TokenMarkovModel()
token_markov.load(TOK_MARKOV_PATH)

# 先頭付近（既存のトークンMarkovを置換）
import json, os, random, MeCab, re
from collections import defaultdict

POS_MODEL_PATH = "app/data/markov_pos_model.json"
os.makedirs("app/data", exist_ok=True)

# 出力を弱めるPOS（連鎖には使うが、文面には極力出さない）
WEAK_OUTPUT_POS = {"助詞", "助動詞", "記号"}

# 文末判定
SENT_END_RE = re.compile(r"[。．.!！?？]$")


class POSMarkovModel:
    # chain_pos: (pos1,pos2) -> [pos3,...]
    # emit: pos -> [surface,...]
    def __init__(self):
        self.chain_pos = defaultdict(list)
        self.emit = defaultdict(list)
        self.tagger = MeCab.Tagger("")

    def _morphs(self, text: str):
        node = self.tagger.parseToNode(text or "")
        while node:
            surface = (node.surface or "").strip()
            feat = node.feature or ""
            if surface and feat:
                pos = feat.split(",")[0]
                yield surface, pos
            node = node.next

    def train_lines(self, lines: list[str]):
        for line in lines:
            toks = list(self._morphs(line.strip()))
            if not toks:
                continue
            pos_seq = ["<BOS>", "<BOS>"] + [p for _, p in toks] + ["<EOS>"]
            for i in range(len(pos_seq) - 2):
                key = (pos_seq[i], pos_seq[i + 1])
                self.chain_pos[key].append(pos_seq[i + 2])
            for surf, pos in toks:
                self.emit[pos].append(surf)

    def _sample(self, arr):
        return random.choice(arr) if arr else None

    def generate(
        self, seed_tokens: list[tuple[str, str]] | None = None, max_steps: int = 60
    ) -> str:
        # 初期キー（POS二連）
        if seed_tokens and len(seed_tokens) >= 2:
            p1, p2 = seed_tokens[0][1], seed_tokens[1][1]
            key = (p1, p2)
            if key not in self.chain_pos:
                key = self._sample(list(self.chain_pos.keys()))
        else:
            key = self._sample(list(self.chain_pos.keys()))
        if not key:
            return ""

        out_surfaces = []
        steps = 0
        while steps < max_steps:
            steps += 1
            nxt_pos = self._sample(self.chain_pos.get(key, []))
            if not nxt_pos or nxt_pos == "<EOS>":
                break
            # 出力語のサンプリング（弱い品詞は低確率で出す）
            cand = self.emit.get(nxt_pos, [])
            if not cand:
                # エミッションが無いPOSはスキップ
                key = (key[1], nxt_pos)
                continue
            surface = self._sample(cand)
            if nxt_pos in WEAK_OUTPUT_POS:
                # 20%だけ出力（つなぎとして最小限）
                if random.random() < 0.2:
                    out_surfaces.append(surface)
            else:
                out_surfaces.append(surface)

            # 句点等で文を締める
            if SENT_END_RE.search(surface):
                break

            key = (key[1], nxt_pos)

        # スペース不要（単純連結）
        return "".join(out_surfaces).strip()

    def dump(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "chain_pos": {"\t".join(k): v for k, v in self.chain_pos.items()},
                    "emit": self.emit,
                },
                f,
                ensure_ascii=False,
            )

    def load(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.chain_pos = defaultdict(list)
        for k, v in data.get("chain_pos", {}).items():
            p1, p2 = k.split("\t")
            self.chain_pos[(p1, p2)] = v
        self.emit = defaultdict(list, data.get("emit", {}))

    # ユーティリティ：シード用にdisplay_wordsからPOS推定が無い場合でも形だけ持たせる
    def guess_pos(self, text: str) -> list[tuple[str, str]]:
        return list(self._morphs(text))


pos_markov = POSMarkovModel()
pos_markov.load(POS_MODEL_PATH)


class LLMLearning:
    """LLM学習用クラス（完全リセット版）"""

    def __init__(self):
        self.templates = []  # 学習したテンプレート（最大10個）
        self.keywords = []  # 学習したキーワード（最大20個）

    def learn_from_odai(self, odai_text: str):
        """お題から学習（完全にシンプル化）"""
        if not odai_text.strip():
            return

        # テンプレート学習のみ（厳格な制限）
        self._learn_templates_strict(odai_text)

    def _learn_templates_strict(self, odai_text: str):
        """完全にゼロから学習（事前定義パターンなし）"""
        if len(self.templates) >= 50:  # より多くのパターンを学習
            return

        import re

        # 学習データから動的にパターンを抽出
        # 「○○」を含むパターンを探す
        if "○○" in odai_text:
            # 既にテンプレート形式の場合はそのまま学習
            if odai_text not in self.templates:
                self.templates.append(odai_text)
                print(f"テンプレート追加: {odai_text} (現在: {len(self.templates)}個)")
        else:
            # 通常のお題からパターンを抽出
            # 名詞部分を「○○」に置き換えてパターン化
            self._extract_pattern_from_odai(odai_text)

    def _extract_pattern_from_odai(self, odai_text: str):
        """お題からパターンを完全にゼロから抽出（事前定義パターンなし）"""
        import re

        # お題の品質チェック
        if not self._is_valid_odai(odai_text):
            return

        # 完全にゼロからパターンを抽出
        # お題の構造を分析してパターンを作成
        self._analyze_odai_structure(odai_text)

    def _analyze_odai_structure(self, odai_text: str):
        """お題の構造を分析してパターンを抽出"""
        import re

        # お題の長さと構造を分析
        if len(odai_text) < 4 or len(odai_text) > 20:
            return

        # 既存のテンプレートと重複しないかチェック
        if odai_text in self.templates:
            return

        # お題の構造パターンを動的に抽出
        # 例：「AIの秘密」→「○○の秘密」
        pattern = self._create_pattern_from_odai(odai_text)

        if pattern and pattern not in self.templates:
            self.templates.append(pattern)
            print(f"構造分析: {odai_text} -> {pattern} (現在: {len(self.templates)}個)")

    def _create_pattern_from_odai(self, odai_text: str):
        """お題からパターンを動的に作成"""
        import re

        # 一般的な構造パターンを動的に検出
        # 「名詞 + の + 形容詞/名詞」パターン
        if re.search(r"(.+?)の(.+?)$", odai_text):
            match = re.search(r"(.+?)の(.+?)$", odai_text)
            if match and len(match.group(1)) >= 2 and len(match.group(1)) <= 8:
                return f"○○の{match.group(2)}"

        # 「名詞 + あるある」パターン
        if re.search(r"(.+?)あるある$", odai_text):
            match = re.search(r"(.+?)あるある$", odai_text)
            if match and len(match.group(1)) >= 2 and len(match.group(1)) <= 8:
                return "○○あるある"

        # 「こんな + 名詞 + は嫌だ」パターン
        if re.search(r"こんな(.+?)は嫌だ$", odai_text):
            match = re.search(r"こんな(.+?)は嫌だ$", odai_text)
            if match and len(match.group(1)) >= 2 and len(match.group(1)) <= 8:
                return "こんな○○は嫌だ"

        # 「名詞 + で困ること」パターン
        if re.search(r"(.+?)で困ること$", odai_text):
            match = re.search(r"(.+?)で困ること$", odai_text)
            if match and len(match.group(1)) >= 2 and len(match.group(1)) <= 8:
                return "○○で困ること"

        # その他の構造パターン
        # 「名詞 + の + 名詞」パターン（一般的）
        if re.search(r"(.+?)の(.+?)$", odai_text):
            match = re.search(r"(.+?)の(.+?)$", odai_text)
            if match and len(match.group(1)) >= 2 and len(match.group(1)) <= 8:
                return f"○○の{match.group(2)}"

        return None

    def _is_valid_odai(self, odai_text: str) -> bool:
        """お題が有効かどうかをチェック"""
        import re

        # 空文字列や短すぎるものは除外
        if not odai_text or len(odai_text.strip()) < 3:
            return False

        # 特殊文字や記号が多すぎるものは除外
        special_chars = r"[\\\/\*\#\@\$\%\^\&\+\=\|\[\]\{\}\(\)\<\>\?\!]"
        if len(re.findall(special_chars, odai_text)) > len(odai_text) * 0.3:
            return False

        # 数字のみのものは除外
        if odai_text.strip().isdigit():
            return False

        # 意味不明な文字列は除外
        if any(char in odai_text for char in ["\1", "\2", "○", "●"]):
            return False

        return True

    def generate_odai(self, seeds: list, count: int) -> list:
        """お題らしい文章を生成（完全に学習データのみ使用）"""
        results = []

        # 学習したテンプレートのみを使用（事前定義パターンなし）
        patterns = self.templates

        # 学習データが不足している場合はエラー
        if not patterns:
            print("⚠️ 学習データが不足しています。まず学習を実行してください。")
            return ["学習データが不足しています。まず学習を実行してください。"]

        # シード単語を適切な名詞にフィルタリング
        good_seeds = [seed for seed in seeds if self._is_good_seed(seed)]
        if not good_seeds:
            good_seeds = seeds[:5]  # フォールバック

        # パターンから生成
        for i in range(count):
            if not patterns or not good_seeds:
                break

            pattern = random.choice(patterns)
            seed = random.choice(good_seeds)
            odai = pattern.replace("○○", seed)

            # 品質チェック
            if (
                len(odai) >= 4
                and len(odai) <= 20
                and odai not in results
                and not odai.endswith("。")
                and not odai.startswith("。")
            ):
                results.append(odai)

        # 学習データのみで生成（補完なし）
        print(f"学習データから生成: {len(results)}個のお題を生成")
        return results[:count]

    def _is_good_seed(self, seed: str) -> bool:
        """シード単語がお題に適しているかチェック"""
        if not seed or len(seed) < 2 or len(seed) > 8:
            return False

        # 数字のみは除外
        if seed.isdigit():
            return False

        # 助詞・助動詞は除外
        particles = {
            "の",
            "が",
            "は",
            "を",
            "に",
            "で",
            "と",
            "から",
            "まで",
            "も",
            "だけ",
            "しか",
        }
        if seed in particles:
            return False

        return True

    def dump(self, path: str):
        """学習データを保存"""
        data = {
            "templates": self.templates,
            "keywords": self.keywords,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self, path: str):
        """学習データを読み込み"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.templates = data.get("templates", [])
                self.keywords = data.get("keywords", [])
        except FileNotFoundError:
            # ファイルが存在しない場合は空で初期化
            self.templates = []
            self.keywords = []


llm_learning = LLMLearning()
llm_learning.load(LLM_LEARNED_DATA_PATH)


# アップロード学習エンドポイント（形態素版）
@app.post("/api/odai/train")
async def train_markov(file: UploadFile = File(...)):
    try:
        print(f"マルコフ学習開始: ファイル名={file.filename}")

        content = (await file.read()).decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        print(f"ファイル読み込み完了: {len(lines)}行")

        if not lines:
            raise HTTPException(status_code=400, detail="有効な行がありません")

        print("マルコフ学習中...")
        pos_markov.train_lines(lines)
        print("学習データを保存中...")
        pos_markov.dump(POS_MODEL_PATH)

        result = {
            "message": f"POSモデル学習完了: {len(lines)} 行",
            "chain_size": len(pos_markov.chain_pos),
        }
        print(f"マルコフ学習完了: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"マルコフ学習エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 生成エンドポイント（形態素モデル使用）
@app.post("/api/odai/generate")
async def generate_odai(
    count: int = Form(30),
    use_display_words: bool = Form(True),
    db: Session = Depends(get_db),
):
    try:
        if not pos_markov.chain_pos:
            pos_markov.load(POS_MODEL_PATH)
        if not pos_markov.chain_pos:
            raise HTTPException(status_code=400, detail="POSマルコフモデルが未学習です")

        # 使う単語は display_words のみ
        words = DisplayWordCRUD.get_all(db)
        seeds = [w.word for w in words]
        if not seeds:
            raise HTTPException(
                status_code=400,
                detail="display_wordsが空です（文章から抽出して追加してください）",
            )

        # シード単語をランダムに選択
        selected_seeds = random.sample(seeds, min(len(seeds), 5))

        # マルコフ連鎖でお題を生成（品質重視）
        results = []
        max_attempts = count * 3  # 品質向上のため試行回数を増やす
        attempts = 0

        while len(results) < count and attempts < max_attempts:
            attempts += 1
            try:
                # シード単語からPOS推定
                seed_tokens = pos_markov.guess_pos(random.choice(selected_seeds))
                if seed_tokens:
                    generated = pos_markov.generate(
                        seed_tokens, max_steps=20
                    )  # ステップ数を制限
                else:
                    # シード単語が使えない場合はランダム生成
                    generated = pos_markov.generate(None, max_steps=20)

                if generated and len(generated.strip()) > 0:
                    generated = generated.strip()
                    # 品質チェック
                    if (
                        len(generated) >= 3
                        and len(generated) <= 25
                        and generated not in results
                        and not generated.endswith("。")  # 句点で終わらない
                        and not generated.startswith("。")
                    ):  # 句点で始まらない
                        results.append(generated)
            except Exception as e:
                print(f"生成エラー: {e}")
                continue

        print(f"マルコフ生成結果: {len(results)}個")
        print(f"生成されたお題: {results[:3] if results else 'なし'}")

        return {"count": len(results), "odai": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# LLM生成エンドポイント


# LLM学習エンドポイント
@app.post("/api/odai/train-llm")
async def train_llm(file: UploadFile = File(...)):
    try:
        print(f"LLM学習開始: ファイル名={file.filename}")

        content = (await file.read()).decode("utf-8", errors="ignore")
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        print(f"ファイル読み込み完了: {len(lines)}行")

        if not lines:
            raise HTTPException(status_code=400, detail="有効な行がありません")

        print("LLM学習データに追加中...")
        print(
            f"学習前: テンプレート={len(llm_learning.templates)}, キーワード={len(llm_learning.keywords)}"
        )
        # LLM学習データに追加
        for i, line in enumerate(lines):
            if i % 100 == 0:
                print(f"学習進行中: {i}/{len(lines)}")
            llm_learning.learn_from_odai(line)
        print(
            f"学習後: テンプレート={len(llm_learning.templates)}, キーワード={len(llm_learning.keywords)}"
        )

        print("学習データを保存中...")
        # 学習データを保存
        llm_learning.dump(LLM_LEARNED_DATA_PATH)

        result = {
            "message": f"LLM学習完了: {len(lines)} 行",
            "templates": len(llm_learning.templates),
            "keywords": len(llm_learning.keywords),
        }
        print(f"LLM学習完了: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"LLM学習エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/odai/generate-llm")
async def generate_odai_llm(
    count: int = Form(30),
    use_display_words: bool = Form(True),
    db: Session = Depends(get_db),
):
    try:
        # 生成数を制限（パフォーマンス向上）
        count = min(count, 50)

        # 使う単語は display_words のみ
        words = DisplayWordCRUD.get_all(db)
        seeds = [w.word for w in words]
        if not seeds:
            raise HTTPException(
                status_code=400,
                detail="display_wordsが空です（文章から抽出して追加してください）",
            )

        # 学習したデータを使用してお題を生成
        print(f"LLM生成開始: seeds={seeds[:5]}, count={count}")
        print(
            f"学習データ: templates={len(llm_learning.templates)}, keywords={len(llm_learning.keywords)}"
        )

        results = llm_learning.generate_odai(seeds, count)

        print(f"LLM生成結果: {len(results)}個")
        print(f"生成されたお題: {results[:3] if results else 'なし'}")

        return {"count": len(results), "odai": results, "method": "llm"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"LLM生成エラー: {e}")
        raise HTTPException(status_code=500, detail=f"LLM生成エラー: {str(e)}")


# モデル保存・読み込みエンドポイント
@app.post("/api/odai/save-model")
async def save_llm_model():
    """LLMモデルを外部ファイルに保存"""
    try:
        # 現在の学習データを保存
        llm_learning.dump(LLM_LEARNED_DATA_PATH)

        # ファイルサイズを取得
        import os

        file_size = (
            os.path.getsize(LLM_LEARNED_DATA_PATH)
            if os.path.exists(LLM_LEARNED_DATA_PATH)
            else 0
        )

        return {
            "message": "LLMモデルを保存しました",
            "file_path": LLM_LEARNED_DATA_PATH,
            "file_size": file_size,
            "templates": len(llm_learning.templates),
            "keywords": len(llm_learning.keywords),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"モデル保存エラー: {str(e)}")


@app.post("/api/odai/load-model")
async def load_llm_model():
    """外部ファイルからLLMモデルを読み込み"""
    try:
        # 学習データを読み込み
        llm_learning.load(LLM_LEARNED_DATA_PATH)

        return {
            "message": "LLMモデルを読み込みました",
            "templates": len(llm_learning.templates),
            "keywords": len(llm_learning.keywords),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"モデル読み込みエラー: {str(e)}")


@app.get("/api/odai/model-info")
async def get_model_info():
    """現在のモデル情報を取得"""
    try:
        return {
            "templates": len(llm_learning.templates),
            "keywords": len(llm_learning.keywords),
            "file_exists": os.path.exists(LLM_LEARNED_DATA_PATH),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"モデル情報取得エラー: {str(e)}")


# 確定お題関連のAPIエンドポイント
@app.get("/api/confirmed-odais")
async def get_confirmed_odais(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """確定お題一覧を取得"""
    try:
        odais = ConfirmedOdaiCRUD.get_all(db, skip=skip, limit=limit)
        return {
            "odais": [
                {
                    "id": odai.id,
                    "odai_text": odai.odai_text,
                    "source": odai.source,
                    "created_at": odai.created_at.isoformat(),
                }
                for odai in odais
            ],
            "total": ConfirmedOdaiCRUD.get_count(db),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"確定お題取得エラー: {str(e)}")


@app.post("/api/confirmed-odais")
async def create_confirmed_odai(
    odai_text: str = Form(...),
    source: str = Form("manual"),
    db: Session = Depends(get_db),
):
    """確定お題を作成"""
    try:
        if not odai_text.strip():
            raise HTTPException(status_code=400, detail="お題テキストが空です")

        confirmed_odai = ConfirmedOdaiCRUD.create(db, odai_text.strip(), source)
        return {
            "message": "確定お題を追加しました",
            "odai": {
                "id": confirmed_odai.id,
                "odai_text": confirmed_odai.odai_text,
                "source": confirmed_odai.source,
                "created_at": confirmed_odai.created_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"確定お題作成エラー: {str(e)}")


@app.delete("/api/confirmed-odais/{odai_id}")
async def delete_confirmed_odai(odai_id: int, db: Session = Depends(get_db)):
    """確定お題を削除"""
    try:
        success = ConfirmedOdaiCRUD.delete(db, odai_id)
        if success:
            return {"message": "確定お題を削除しました"}
        else:
            raise HTTPException(status_code=404, detail="確定お題が見つかりません")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"確定お題削除エラー: {str(e)}")
