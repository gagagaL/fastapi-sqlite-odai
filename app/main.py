from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
import os
import re
import MeCab
import random
from datetime import datetime
from collections import defaultdict

from .database.connection import get_db, init_db
from .database.crud import (
    DisplayWordCRUD,
    ConfirmedOdaiCRUD,
    OdaiRatingCRUD,
)
from .database.models import (
    DisplayWord,
    ConfirmedOdai,
    OdaiRating,
)
from .config import get_settings
from .analysis.fourth_force_context_learner import FourthForceContextLearner
from .analysis.fourth_force_generator import FourthForceGenerator
from .analysis import ai_force_generator
from .analysis.pattern_based_generator import pattern_generator


# データディレクトリの作成
os.makedirs("app/data", exist_ok=True)

# 設定読み込み
settings = get_settings()

# FastAPIアプリケーション初期化
app = FastAPI(
    title=settings.app_name,
    description="大喜利のお題を自動生成",
    version="2.0.0",
)

# 静的ファイルとテンプレートの設定
os.makedirs("app/static/css", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True)
os.makedirs("app/templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# 位置設定ファイルのパス
POSITION_SETTINGS_FILE = "app/data/position_settings.json"
WORD_SETTINGS_FILE = "app/data/word_settings.json"


def get_position_settings():
    """表示設定を取得"""
    try:
        if os.path.exists(POSITION_SETTINGS_FILE):
            with open(POSITION_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "top_position": 50,
            "font_size": 48,
            "width_px": 800,
        }
    except Exception as e:
        print(f"表示設定読み込みエラー: {e}")
        return {"top_position": 50, "font_size": 48, "width_px": 800}


def save_display_settings(top_position, font_size, width_px):
    """表示設定を保存"""
    try:
        os.makedirs(os.path.dirname(POSITION_SETTINGS_FILE), exist_ok=True)
        settings = {
            "top_position": top_position,
            "font_size": font_size,
            "width_px": width_px,
        }
        with open(POSITION_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"表示設定保存エラー: {e}")
        return False


def get_word_settings():
    """単語表示設定を取得"""
    try:
        if os.path.exists(WORD_SETTINGS_FILE):
            with open(WORD_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "word_top_position": 20,
        }
    except Exception as e:
        print(f"単語表示設定読み込みエラー: {e}")
        return {"word_top_position": 20}


def save_word_settings(word_top_position):
    """単語表示設定を保存"""
    try:
        os.makedirs(os.path.dirname(WORD_SETTINGS_FILE), exist_ok=True)
        settings = {
            "word_top_position": word_top_position,
        }
        with open(WORD_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"単語表示設定保存エラー: {e}")
        return False


# 第四の力のインスタンス
fourth_force_learner = FourthForceContextLearner()
fourth_force_generator = FourthForceGenerator(fourth_force_learner)

# 第四の力の学習データパス
FOURTH_FORCE_DATA_PATH = "app/data/fourth_force_learning_data.json"

# 第四の力の学習データを読み込み
fourth_force_learner.load_learning_data(FOURTH_FORCE_DATA_PATH)


@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    init_db()
    print(f"🚀 {settings.app_name} が起動しました！")
    print(f"📖 API仕様: http://localhost:8000/docs")


# ============================================
# Web画面のルート
# ============================================


@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    """トップページ"""
    # 統計情報を取得
    display_words = DisplayWordCRUD.get_all(db)
    confirmed_odais = ConfirmedOdaiCRUD.get_all(db, skip=0, limit=1000)

    stats = {
        "word_count": len(display_words),
        "topic_count": len(confirmed_odais),
    }

    # 最新のお題を取得
    recent_topics = []
    for odai in confirmed_odais[:5]:  # 最新5件
        recent_topics.append({
            "topic_text": odai.odai_text,
            "is_generated": odai.source != "manual",
            "created_at": odai.created_at,
        })

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": settings.app_name,
            "stats": stats,
            "recent_topics": recent_topics,
        },
    )


@app.get("/admin")
async def admin_page(request: Request):
    """管理画面"""
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "title": settings.app_name,
        },
    )


@app.get("/display")
async def display_page(request: Request, db: Session = Depends(get_db)):
    """表示画面"""
    words = DisplayWordCRUD.get_all(db)
    display_settings = get_position_settings()
    word_settings = get_word_settings()

    return templates.TemplateResponse(
        "display.html",
        {
            "request": request,
            "title": settings.app_name,
            "words": [{"word": w.word, "pos": w.pos} for w in words],
            "top_position": display_settings.get("top_position", 50),
            "font_size": display_settings.get("font_size", 48),
            "width_px": display_settings.get("width_px", 800),
            "word_top_position": word_settings.get("word_top_position", 20),
        },
    )


# ============================================
# DisplayWord APIエンドポイント
# ============================================


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


@app.delete("/api/display/words/all")
async def delete_all_display_words(db: Session = Depends(get_db)):
    """登録済み単語を全削除"""
    try:
        DisplayWordCRUD.delete_all(db)
        return {"message": "すべての単語を削除しました"}
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
    """文章から単語を抽出して登録"""
    if not sentence.strip():
        raise HTTPException(status_code=400, detail="文章が空です")
    try:
        tagger = MeCab.Tagger("")
        result = tagger.parse(sentence)

        target_heads = {"名詞", "動詞", "形容詞", "形容動詞", "形容動詞語幹", "副詞"}
        allow_re = re.compile(
            r"^[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF10-\uFF19A-Za-z0-9ー\-]+$"
        )

        picked = []
        for line in result.strip().split("\n"):
            if not line or line == "EOS":
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue

            surface = parts[0].strip()
            pos_full = parts[4]
            pos = pos_full.split("-")[0] if pos_full else ""

            if pos not in target_heads:
                continue
            if not surface or not allow_re.match(surface):
                continue

            picked.append({"word": surface, "pos": pos})

        added_count = 0
        for item in picked:
            try:
                DisplayWordCRUD.create(db, item["word"], item["pos"])
                added_count += 1
            except Exception:
                pass

        return {
            "message": f"{added_count}個の単語を登録しました",
            "added_count": added_count,
            "extracted_words": picked,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ConfirmedOdai APIエンドポイント
# ============================================


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
                    "is_active": odai.is_active,
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


@app.delete("/api/confirmed-odais/all")
async def delete_all_confirmed_odais(db: Session = Depends(get_db)):
    """確定お題を全削除"""
    try:
        deleted_count = ConfirmedOdaiCRUD.delete_all(db)
        return {"message": f"すべての確定お題を削除しました（{deleted_count}件）"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"確定お題全削除エラー: {str(e)}")


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


@app.post("/api/confirmed-odais/{odai_id}/activate")
async def activate_odai(odai_id: int, db: Session = Depends(get_db)):
    """お題を出題中に設定"""
    try:
        success = ConfirmedOdaiCRUD.set_active(db, odai_id)
        if success:
            active_odai = ConfirmedOdaiCRUD.get_active(db)
            return {
                "message": "お題を出題中に設定しました",
                "active_odai": {
                    "id": active_odai.id,
                    "odai_text": active_odai.odai_text,
                    "source": active_odai.source,
                    "created_at": active_odai.created_at.isoformat(),
                }
                if active_odai
                else None,
            }
        else:
            raise HTTPException(status_code=404, detail="確定お題が見つかりません")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"お題出題設定エラー: {str(e)}")


@app.post("/api/confirmed-odais/{odai_id}/deactivate")
async def deactivate_odai(odai_id: int, db: Session = Depends(get_db)):
    """お題を非出題中に設定"""
    try:
        success = ConfirmedOdaiCRUD.set_inactive(db, odai_id)
        if success:
            return {"message": "お題を非出題中に設定しました"}
        else:
            raise HTTPException(status_code=404, detail="確定お題が見つかりません")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"お題非出題設定エラー: {str(e)}")


@app.get("/api/confirmed-odais/active")
async def get_active_odai(db: Session = Depends(get_db)):
    """現在出題中のお題を取得"""
    try:
        active_odai = ConfirmedOdaiCRUD.get_active(db)
        if active_odai:
            return {
                "active_odai": {
                    "id": active_odai.id,
                    "odai_text": active_odai.odai_text,
                    "source": active_odai.source,
                    "created_at": active_odai.created_at.isoformat(),
                }
            }
        else:
            return {"active_odai": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"出題中お題取得エラー: {str(e)}")


# ============================================
# 表示設定 APIエンドポイント
# ============================================


@app.get("/api/display/position")
async def get_display_position():
    """表示設定を取得"""
    try:
        settings = get_position_settings()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"表示設定取得エラー: {str(e)}")


@app.post("/api/display/position")
async def update_display_position(
    top_position: int = Form(...), font_size: int = Form(48), width_px: int = Form(800)
):
    """表示設定を更新"""
    try:
        if not (0 <= top_position <= 100):
            raise HTTPException(
                status_code=400, detail="位置は0-100の範囲で指定してください"
            )
        if not (12 <= font_size <= 200):
            raise HTTPException(
                status_code=400, detail="フォントサイズは12-200の範囲で指定してください"
            )
        if not (200 <= width_px <= 2000):
            raise HTTPException(
                status_code=400, detail="横幅は200-2000の範囲で指定してください"
            )

        success = save_display_settings(top_position, font_size, width_px)
        if success:
            return {
                "message": "表示設定を更新しました",
                "settings": get_position_settings(),
            }
        else:
            raise HTTPException(status_code=500, detail="設定の保存に失敗しました")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"表示設定更新エラー: {str(e)}")


@app.post("/api/display/word-settings")
async def update_word_settings(word_top_position: int = Form(...)):
    """単語表示設定を更新"""
    try:
        if not (0 <= word_top_position <= 100):
            raise HTTPException(
                status_code=400, detail="位置は0-100の範囲で指定してください"
            )

        success = save_word_settings(word_top_position)
        if success:
            return {
                "message": "単語表示設定を更新しました",
                "settings": get_word_settings(),
            }
        else:
            raise HTTPException(status_code=500, detail="設定の保存に失敗しました")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"単語表示設定更新エラー: {str(e)}")


@app.get("/api/display/word-settings")
async def get_word_display_settings():
    """単語表示設定を取得"""
    try:
        settings = get_word_settings()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"単語表示設定取得エラー: {str(e)}")


# ============================================
# お題評価 APIエンドポイント
# ============================================


@app.post("/api/odai/rate")
async def rate_odai(
    odai_text: str = Form(...),
    rating: int = Form(...),
    source: str = Form("unknown"),
    feedback: str = Form(None),
    db: Session = Depends(get_db),
):
    """お題を評価"""
    try:
        if not 1 <= rating <= 5:
            raise HTTPException(
                status_code=400, detail="評価は1-5の範囲で指定してください"
            )

        rating_obj = OdaiRatingCRUD.create(
            db, odai_text=odai_text, rating=rating, source=source, feedback=feedback
        )

        # 第四の力の自動学習
        auto_learned = False
        if source == "fourth_force_context":
            if rating >= 4:
                try:
                    learned = fourth_force_learner.learn_from_odai(odai_text)
                    if learned:
                        fourth_force_learner.save_learning_data(FOURTH_FORCE_DATA_PATH)
                        auto_learned = True
                except Exception as e:
                    print(f"第四の力高評価自動学習エラー: {e}")

        return {
            "message": f"お題を評価しました（評価: {rating}）"
            + (" - 自動学習も実行しました" if auto_learned else ""),
            "auto_learned": auto_learned,
            "rating": {
                "id": rating_obj.id,
                "odai_text": rating_obj.odai_text,
                "rating": rating_obj.rating,
                "source": rating_obj.source,
                "created_at": rating_obj.created_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"評価エラー: {str(e)}")


@app.get("/api/odai/ratings/high-rated")
async def get_high_rated_odais(
    min_rating: int = 4, limit: int = 50, db: Session = Depends(get_db)
):
    """高評価のお題を取得"""
    try:
        ratings = OdaiRatingCRUD.get_high_rated_odais(db, min_rating, limit)
        return {
            "ratings": [
                {
                    "id": rating.id,
                    "odai_text": rating.odai_text,
                    "rating": rating.rating,
                    "source": rating.source,
                    "feedback": rating.feedback,
                    "created_at": rating.created_at.isoformat(),
                }
                for rating in ratings
            ],
            "count": len(ratings),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"高評価お題取得エラー: {str(e)}")


@app.get("/api/odai/ratings/stats")
async def get_rating_stats(db: Session = Depends(get_db)):
    """評価統計を取得"""
    try:
        all_ratings = db.query(OdaiRating).all()

        if not all_ratings:
            return {
                "total_count": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "source_distribution": {},
            }

        total = len(all_ratings)
        avg = sum(r.rating for r in all_ratings) / total

        rating_dist = {}
        for i in range(1, 6):
            rating_dist[str(i)] = len([r for r in all_ratings if r.rating == i])

        source_dist = {}
        for r in all_ratings:
            source = r.source or "unknown"
            source_dist[source] = source_dist.get(source, 0) + 1

        return {
            "total_count": total,
            "average_rating": round(avg, 2),
            "rating_distribution": rating_dist,
            "source_distribution": source_dist,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"評価統計取得エラー: {str(e)}")


# ============================================
# 第四の力 APIエンドポイント
# ============================================


@app.post("/api/fourth-force/learn")
async def learn_fourth_force_patterns(file: UploadFile = File(...)):
    """第四の力の文脈学習"""
    try:
        if not file.filename.endswith((".txt", ".json")):
            raise HTTPException(
                status_code=400,
                detail="テキストファイルまたはJSONファイルをアップロードしてください",
            )

        content = await file.read()
        text_content = content.decode("utf-8")

        if file.filename.endswith(".txt"):
            lines = text_content.strip().split("\n")
            learned_count = 0

            for line in lines:
                line = line.strip()
                if line:
                    learned = fourth_force_learner.learn_from_odai(line)
                    if learned:
                        learned_count += 1

            fourth_force_learner.save_learning_data(FOURTH_FORCE_DATA_PATH)

            return {
                "message": f"第四の力: {learned_count}個のお題から学習しました",
                "learned_count": learned_count,
                "stats": fourth_force_learner.get_learning_stats(),
            }

        elif file.filename.endswith(".json"):
            try:
                data = json.loads(text_content)
                if isinstance(data, list):
                    learned_count = 0
                    for item in data:
                        odai_text = None
                        if isinstance(item, str):
                            odai_text = item
                        elif isinstance(item, dict) and "odai_text" in item:
                            odai_text = item["odai_text"]

                        if odai_text:
                            learned = fourth_force_learner.learn_from_odai(odai_text)
                            if learned:
                                learned_count += 1

                    fourth_force_learner.save_learning_data(FOURTH_FORCE_DATA_PATH)

                    return {
                        "message": f"第四の力: {learned_count}個のお題から学習しました",
                        "learned_count": learned_count,
                        "stats": fourth_force_learner.get_learning_stats(),
                    }
                else:
                    raise HTTPException(
                        status_code=400, detail="JSONファイルの形式が正しくありません"
                    )
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="JSONファイルの解析に失敗しました"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第四の力学習エラー: {str(e)}")


@app.post("/api/fourth-force/generate")
async def generate_fourth_force_odai(
    count: int = Form(10), use_words: bool = Form(True), db: Session = Depends(get_db)
):
    """第四の力でお題を生成"""
    try:
        words_to_use = []
        if use_words:
            words = db.query(DisplayWord).all()
            words_to_use = [word.word for word in words if word.word]

        if not words_to_use:
            return {
                "error": "第四の力: 使用する単語がありません。まず単語を登録してください。",
                "generated_odais": [],
                "stats": fourth_force_generator.get_generation_stats(),
            }

        generated_odais = fourth_force_generator.generate_from_words(
            words_to_use, count=count
        )

        if not generated_odais:
            return {
                "error": "第四の力: お題の生成に失敗しました。学習データが不足している可能性があります。",
                "generated_odais": [],
                "stats": fourth_force_generator.get_generation_stats(),
            }

        return {
            "message": f"第四の力: {len(generated_odais)}個のお題を生成しました",
            "generated_odais": [
                {
                    "text": odai["text"],
                    "source": odai.get("source", "fourth_force_context"),
                    "method": odai.get("method", "unknown"),
                }
                for odai in generated_odais
            ],
            "saved_count": 0,
            "stats": fourth_force_generator.get_generation_stats(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第四の力生成エラー: {str(e)}")


@app.get("/api/fourth-force/stats")
async def get_fourth_force_stats():
    """第四の力の学習統計を取得"""
    try:
        return {
            "learning_stats": fourth_force_learner.get_learning_stats(),
            "generation_stats": fourth_force_generator.get_generation_stats(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第四の力統計取得エラー: {str(e)}")


@app.post("/api/fourth-force/reset")
async def reset_fourth_force_learning():
    """第四の力の学習データをリセット"""
    try:
        fourth_force_learner.reset()
        fourth_force_learner.save_learning_data(FOURTH_FORCE_DATA_PATH)

        return {
            "message": "第四の力の学習データをリセットしました",
            "stats": fourth_force_learner.get_learning_stats(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第四の力リセットエラー: {str(e)}")


@app.post("/api/fourth-force/learn-from-high-ratings")
async def learn_fourth_force_from_high_ratings(
    min_rating: int = Form(4), limit: int = Form(50), db: Session = Depends(get_db)
):
    """高評価のお題から第四の力を学習"""
    try:
        high_rated = OdaiRatingCRUD.get_high_rated_odais(db, min_rating, limit)

        if not high_rated:
            return {
                "message": "高評価のお題が見つかりません",
                "learned_count": 0,
                "stats": fourth_force_learner.get_learning_stats(),
            }

        learned_count = 0
        for rating in high_rated:
            learned = fourth_force_learner.learn_from_odai(rating.odai_text)
            if learned:
                learned_count += 1

        fourth_force_learner.save_learning_data(FOURTH_FORCE_DATA_PATH)

        return {
            "message": f"第四の力: 高評価のお題{learned_count}個から学習しました",
            "learned_count": learned_count,
            "stats": fourth_force_learner.get_learning_stats(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第四の力高評価学習エラー: {str(e)}")


@app.post("/api/fourth-force/save-model")
async def save_fourth_force_model(
    model_name: str = Form(...),
    description: str = Form(""),
):
    """第四の力モデルを保存"""
    try:
        if not model_name.strip():
            raise HTTPException(status_code=400, detail="モデル名が空です")

        sanitized_name = re.sub(r'[^\w\-]', '_', model_name.strip())

        model_dir = "app/data/fourth_force_models"
        os.makedirs(model_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_file = os.path.join(model_dir, f"{sanitized_name}_{timestamp}.json")

        model_data = {
            "model_name": sanitized_name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "learning_stats": fourth_force_learner.get_learning_stats(),
            "context_patterns": {
                k: dict(v) for k, v in fourth_force_learner.context_patterns.items()
            },
            "templates": fourth_force_learner.templates,
            "word_info": dict(fourth_force_learner.word_info),
        }

        with open(model_file, "w", encoding="utf-8") as f:
            json.dump(model_data, f, ensure_ascii=False, indent=2)

        file_size = os.path.getsize(model_file)

        return {
            "message": f"第四の力モデル '{sanitized_name}' を保存しました",
            "model_name": sanitized_name,
            "file_path": model_file,
            "file_size": file_size,
            "learning_stats": fourth_force_learner.get_learning_stats(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"モデル保存エラー: {str(e)}")


@app.get("/api/fourth-force/models")
async def list_fourth_force_models():
    """保存された第四の力モデル一覧を取得"""
    try:
        model_dir = "app/data/fourth_force_models"
        os.makedirs(model_dir, exist_ok=True)

        models = []
        for filename in os.listdir(model_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(model_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        model_data = json.load(f)

                    file_size = os.path.getsize(filepath)

                    models.append({
                        "filename": filename,
                        "model_name": model_data.get("model_name", filename),
                        "description": model_data.get("description", ""),
                        "created_at": model_data.get("created_at", ""),
                        "file_size": file_size,
                        "learning_stats": model_data.get("learning_stats", {}),
                    })
                except Exception as e:
                    print(f"モデルファイル読み込みエラー {filename}: {e}")

        models.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "models": models,
            "total_count": len(models),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"モデル一覧取得エラー: {str(e)}")


@app.post("/api/fourth-force/load-model")
async def load_fourth_force_model(
    model_name: str = Form(...), db: Session = Depends(get_db)
):
    """第四の力モデルを読み込み"""
    try:
        model_dir = "app/data/fourth_force_models"
        model_file = None

        for filename in os.listdir(model_dir):
            if filename.startswith(model_name) and filename.endswith(".json"):
                model_file = os.path.join(model_dir, filename)
                break

        if not model_file or not os.path.exists(model_file):
            raise HTTPException(
                status_code=404, detail=f"モデル '{model_name}' が見つかりません"
            )

        with open(model_file, "r", encoding="utf-8") as f:
            model_data = json.load(f)

        fourth_force_learner.context_patterns = defaultdict(
            lambda: defaultdict(lambda: {"count": 0, "examples": []}),
            {
                k: defaultdict(lambda: {"count": 0, "examples": []}, v)
                for k, v in model_data.get("context_patterns", {}).items()
            },
        )
        fourth_force_learner.templates = model_data.get("templates", [])
        fourth_force_learner.word_info = defaultdict(
            lambda: {"pos": "", "examples": []}, model_data.get("word_info", {})
        )

        fourth_force_learner.save_learning_data(FOURTH_FORCE_DATA_PATH)

        return {
            "message": f"第四の力モデル '{model_name}' を読み込みました",
            "model_name": model_data.get("model_name", model_name),
            "description": model_data.get("description", ""),
            "created_at": model_data.get("created_at", ""),
            "learning_stats": fourth_force_learner.get_learning_stats(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"モデル読み込みエラー: {str(e)}")


@app.delete("/api/fourth-force/delete-model")
async def delete_fourth_force_model(model_name: str = Form(...)):
    """第四の力モデルを削除"""
    try:
        model_dir = "app/data/fourth_force_models"
        model_file = None

        for filename in os.listdir(model_dir):
            if filename.startswith(model_name) and filename.endswith(".json"):
                model_file = os.path.join(model_dir, filename)
                break

        if not model_file or not os.path.exists(model_file):
            raise HTTPException(
                status_code=404, detail=f"モデル '{model_name}' が見つかりません"
            )

        os.remove(model_file)

        return {
            "message": f"第四の力モデル '{model_name}' を削除しました",
            "deleted_file": os.path.basename(model_file),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"モデル削除エラー: {str(e)}")


# ============================================
# 第六勢力（AI + 参考お題）APIエンドポイント
# ============================================


def _get_ai_config():
    """AI API設定を取得（フォールバック付き）"""
    s = get_settings()
    provider = s.ai_provider or "gemini"
    api_key = s.gemini_api_key if provider == "gemini" else s.openai_api_key

    if provider == "gemini" and s.openai_api_key:
        fallback_key = s.openai_api_key
        fallback_provider = "openai"
    elif provider == "openai" and s.gemini_api_key:
        fallback_key = s.gemini_api_key
        fallback_provider = "gemini"
    else:
        fallback_key = ""
        fallback_provider = ""

    return api_key, provider, fallback_key, fallback_provider


@app.post("/api/sixth-force/learn")
async def learn_sixth_force(file: UploadFile = File(...)):
    """第六勢力の参考お題を学習"""
    try:
        if not file.filename.endswith((".txt", ".json")):
            raise HTTPException(
                status_code=400,
                detail="テキストファイルまたはJSONファイルをアップロードしてください",
            )

        content = await file.read()
        text_content = content.decode("utf-8")

        if file.filename.endswith(".txt"):
            new_count, total = ai_force_generator.learn_from_text(text_content)
            return {
                "message": f"第六勢力: {new_count}個の参考お題を学習しました（合計: {total}個）",
                "new_count": new_count,
                "total": total,
                "stats": ai_force_generator.get_reference_stats(),
            }
        elif file.filename.endswith(".json"):
            try:
                data = json.loads(text_content)
                if not isinstance(data, list):
                    raise HTTPException(
                        status_code=400,
                        detail="JSONファイルは配列形式にしてください",
                    )
                new_count, total = ai_force_generator.learn_from_json(data)
                return {
                    "message": f"第六勢力: {new_count}個の参考お題を学習しました（合計: {total}個）",
                    "new_count": new_count,
                    "total": total,
                    "stats": ai_force_generator.get_reference_stats(),
                }
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="JSONファイルの解析に失敗しました"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第六勢力学習エラー: {str(e)}")


@app.post("/api/sixth-force/generate")
async def generate_sixth_force_odai(
    count: int = Form(10),
    use_words: bool = Form(True),
    db: Session = Depends(get_db),
):
    """第六勢力でお題を生成（AI + 参考お題）"""
    try:
        words_to_use = []
        if use_words:
            words = db.query(DisplayWord).all()
            words_to_use = [word.word for word in words if word.word]

        if not words_to_use:
            return {
                "error": "第六勢力: 使用する単語がありません。まず単語を登録してください。",
                "generated_odais": [],
            }

        api_key, provider, fallback_key, fallback_provider = _get_ai_config()

        generated_odais = await ai_force_generator.generate_sixth_force(
            words_to_use, count=count, api_key=api_key, provider=provider,
            fallback_key=fallback_key, fallback_provider=fallback_provider
        )

        if not generated_odais:
            return {
                "error": "第六勢力: お題の生成に失敗しました。",
                "generated_odais": [],
            }

        for odai in generated_odais:
            pattern_generator.learn_from_odai(odai["text"], source="sixth_force")

        return {
            "message": f"第六勢力: {len(generated_odais)}個のお題を生成しました",
            "generated_odais": [
                {
                    "text": odai["text"],
                    "source": odai.get("source", "sixth_force_ai"),
                    "method": odai.get("method", "ai_with_reference"),
                    "quality_score": odai.get("quality_score", 0.5),
                }
                for odai in generated_odais
            ],
            "stats": ai_force_generator.get_reference_stats(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第六勢力生成エラー: {str(e)}")


@app.get("/api/sixth-force/stats")
async def get_sixth_force_stats():
    """第六勢力の統計を取得"""
    try:
        return {
            "stats": ai_force_generator.get_reference_stats(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"第六勢力統計取得エラー: {str(e)}"
        )


@app.post("/api/sixth-force/reset")
async def reset_sixth_force():
    """第六勢力の参考お題をリセット"""
    try:
        ai_force_generator.reset_reference_odais()
        return {
            "message": "第六勢力の参考お題をリセットしました",
            "stats": ai_force_generator.get_reference_stats(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"第六勢力リセットエラー: {str(e)}"
        )


# ============================================
# 第七勢力（AI自由生成）APIエンドポイント
# ============================================


@app.post("/api/seventh-force/generate")
async def generate_seventh_force_odai(
    count: int = Form(10),
    use_words: bool = Form(True),
    db: Session = Depends(get_db),
):
    """第七勢力でお題を生成（AI自由生成）"""
    try:
        words_to_use = []
        if use_words:
            words = db.query(DisplayWord).all()
            words_to_use = [word.word for word in words if word.word]

        if not words_to_use:
            return {
                "error": "第七勢力: 使用する単語がありません。まず単語を登録してください。",
                "generated_odais": [],
            }

        api_key, provider, fallback_key, fallback_provider = _get_ai_config()

        generated_odais = await ai_force_generator.generate_seventh_force(
            words_to_use, count=count, api_key=api_key, provider=provider,
            fallback_key=fallback_key, fallback_provider=fallback_provider
        )

        if not generated_odais:
            return {
                "error": "第七勢力: お題の生成に失敗しました。",
                "generated_odais": [],
            }

        for odai in generated_odais:
            pattern_generator.learn_from_odai(odai["text"], source="seventh_force")

        return {
            "message": f"第七勢力: {len(generated_odais)}個のお題を生成しました",
            "generated_odais": [
                {
                    "text": odai["text"],
                    "source": odai.get("source", "seventh_force_ai"),
                    "method": odai.get("method", "ai_free_generation"),
                    "quality_score": odai.get("quality_score", 0.5),
                }
                for odai in generated_odais
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第七勢力生成エラー: {str(e)}")


# ============================================
# 第八勢力（突飛な設定 + 明確な導線）APIエンドポイント
# ============================================


@app.post("/api/eighth-force/generate")
async def generate_eighth_force_odai(
    count: int = Form(10),
    use_words: bool = Form(True),
    db: Session = Depends(get_db),
):
    """第八勢力でお題を生成（突飛な設定 + 明確な回答導線）"""
    try:
        words_to_use = []
        if use_words:
            words = db.query(DisplayWord).all()
            words_to_use = [word.word for word in words if word.word]

        if not words_to_use:
            return {
                "error": "第八勢力: 使用する単語がありません。まず単語を登録してください。",
                "generated_odais": [],
            }

        api_key, provider, fallback_key, fallback_provider = _get_ai_config()

        generated_odais = await ai_force_generator.generate_eighth_force(
            words_to_use, count=count, api_key=api_key, provider=provider,
            fallback_key=fallback_key, fallback_provider=fallback_provider
        )

        if not generated_odais:
            return {
                "error": "第八勢力: お題の生成に失敗しました。",
                "generated_odais": [],
            }

        for odai in generated_odais:
            pattern_generator.learn_from_odai(odai["text"], source="eighth_force")

        return {
            "message": f"第八勢力: {len(generated_odais)}個のお題を生成しました",
            "generated_odais": [
                {
                    "text": odai["text"],
                    "source": odai.get("source", "eighth_force_ai"),
                    "method": odai.get("method", "ai_creative_guided"),
                    "quality_score": odai.get("quality_score", 0.5),
                }
                for odai in generated_odais
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"第八勢力生成エラー: {str(e)}")


# ============================================
# パターン学習型ローカル生成 APIエンドポイント
# ============================================


@app.post("/api/pattern-local/generate")
async def generate_pattern_local_odai(
    count: int = Form(10),
    use_words: bool = Form(True),
    db: Session = Depends(get_db),
):
    """パターン学習型ローカル生成（AI不要）"""
    try:
        words_to_use = []
        if use_words:
            words = db.query(DisplayWord).all()
            words_to_use = [word.word for word in words if word.word]

        if not words_to_use:
            return {
                "error": "使用する単語がありません。まず単語を登録してください。",
                "generated_odais": [],
            }

        stats = pattern_generator.get_stats()
        if stats["pattern_count"] == 0:
            return {
                "error": "学習済みパターンがありません。先にAI生成を実行してパターンを学習してください。",
                "generated_odais": [],
            }

        generated_odais = pattern_generator.generate(words_to_use, count=count)

        if not generated_odais:
            return {
                "error": "お題の生成に失敗しました。パターン数が不足している可能性があります。",
                "generated_odais": [],
            }

        return {
            "message": f"パターン学習型: {len(generated_odais)}個のお題を生成しました（{stats['pattern_count']}パターンから）",
            "generated_odais": [
                {
                    "text": odai["text"],
                    "source": "pattern_local",
                    "method": "pattern_based",
                    "quality_score": odai.get("quality_score", 0.7),
                }
                for odai in generated_odais
            ],
            "stats": stats,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"パターン生成エラー: {str(e)}")


@app.get("/api/pattern-local/stats")
async def get_pattern_local_stats():
    """パターン学習型の統計を取得"""
    try:
        return {"stats": pattern_generator.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"統計取得エラー: {str(e)}")


@app.post("/api/pattern-local/reset")
async def reset_pattern_local():
    """学習済みパターンをリセット"""
    try:
        pattern_generator.reset()
        return {
            "message": "学習済みパターンをリセットしました",
            "stats": pattern_generator.get_stats(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"リセットエラー: {str(e)}")


@app.post("/api/strict-words/generate")
async def generate_strict_words_odai(
    count: int = Form(10),
    use_words: bool = Form(True),
    db: Session = Depends(get_db),
):
    """登録単語のみ厳密使用でお題を生成"""
    try:
        words_to_use = []
        if use_words:
            words = db.query(DisplayWord).all()
            words_to_use = [word.word for word in words if word.word]

        if not words_to_use:
            return {
                "error": "使用する単語がありません。まず単語を登録してください。",
                "generated_odais": [],
            }

        api_key, provider, fallback_key, fallback_provider = _get_ai_config()

        generated_odais = await ai_force_generator.generate_strict_words_only(
            words_to_use, count=count, api_key=api_key, provider=provider,
            fallback_key=fallback_key, fallback_provider=fallback_provider
        )

        if not generated_odais:
            return {
                "error": "お題の生成に失敗しました。",
                "generated_odais": [],
            }

        for odai in generated_odais:
            pattern_generator.learn_from_odai(odai["text"], source="strict_words")

        return {
            "message": f"登録単語のみ厳密使用: {len(generated_odais)}個のお題を生成しました",
            "generated_odais": [
                {
                    "text": odai["text"],
                    "source": odai.get("source", "strict_words_only"),
                    "method": odai.get("method", "ai_strict_words"),
                    "quality_score": odai.get("quality_score", 0.5),
                }
                for odai in generated_odais
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登録単語のみ生成エラー: {str(e)}")


# ============================================
# AI設定 APIエンドポイント
# ============================================


@app.get("/api/ai/config")
async def get_ai_config():
    """AI設定を取得（APIキーは非表示）"""
    try:
        api_key, provider = _get_ai_config()
        return {
            "provider": provider,
            "has_api_key": bool(api_key),
            "api_key_preview": (
                f"{api_key[:8]}..."
                if api_key and len(api_key) > 8
                else ""
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI設定取得エラー: {str(e)}")
