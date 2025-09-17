from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import random
import logging
import os
import tempfile

from app.database.database import get_db
from app.database.crud import OgiriTopicCRUD, ExtractedWordCRUD
from app.analysis.markov_generator import MarkovChainGenerator

router = APIRouter(
    prefix="/api/odai",
    tags=["odai"]
)

logger = logging.getLogger(__name__)

# マルコフ連鎖生成器のインスタンス
markov_generator = MarkovChainGenerator(order=2)

@router.post("/generate")
async def generate_odai(
    count: int = Form(10),
    use_words: bool = Form(True),
    db: Session = Depends(get_db)
):
    """マルコフ連鎖を使ってお題を生成"""
    try:
        # 訓練データがロードされているか確認
        if not markov_generator.model:
            return {
                "error": "マルコフモデルが学習されていません。先にお題ファイルをアップロードしてください。"
            }
        
        # ランダムな単語を取得（シード用）
        seed_words = []
        if use_words:
            words = ExtractedWordCRUD.get_all(db, limit=50)
            seed_words = [word.word for word in words if len(word.word) >= 2]
            random.shuffle(seed_words)
            seed_words = seed_words[:20]  # 最大20個まで
        
        # お題生成
        odai_list = markov_generator.generate_variations(
            count=count,
            max_words=20,
            seeds=seed_words if seed_words else None
        )
        
        # 生成結果
        return {
            "message": f"{len(odai_list)}個のお題を生成しました",
            "odai_list": odai_list,
            "seed_words_used": seed_words if use_words else []
        }
    except Exception as e:
        logger.error(f"お題生成エラー: {e}")
        return {"error": str(e)}

@router.post("/train")
async def train_markov_model(
    file: UploadFile = File(...),
):
    """お題ファイルをアップロードして学習"""
    try:
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name
        
        # マルコフモデルを学習
        success = markov_generator.train_from_file(temp_path)
        
        # 一時ファイルを削除
        os.unlink(temp_path)
        
        if success:
            return {
                "message": "マルコフモデルの学習が完了しました",
                "model_states": len(markov_generator.model),
                "start_states": len(markov_generator.start_states)
            }
        else:
            return {"error": "学習に失敗しました"}
            
    except Exception as e:
        logger.error(f"マルコフモデル学習エラー: {e}")
        return {"error": str(e)}

@router.post("/save")
async def save_generated_odai(
    odai_list: List[str] = Form(...),
    db: Session = Depends(get_db)
):
    """生成されたお題を保存"""
    try:
        saved_count = 0
        for odai in odai_list:
            if odai.strip():
                OgiriTopicCRUD.create(db, "マルコフ生成お題", odai)
                saved_count += 1
        
        return {
            "message": f"{saved_count}個のお題を保存しました",
            "saved_count": saved_count
        }
    except Exception as e:
        logger.error(f"お題保存エラー: {e}")
        return {"error": str(e)}

@router.get("/list")
async def list_saved_odai(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """保存されたお題のリストを取得"""
    try:
        topics = OgiriTopicCRUD.get_all(db)
        
        if not topics:
            return {
                "message": "お題が見つかりません",
                "topics": []
            }
        
        topics_data = [
            {
                "id": topic.id,
                "title": topic.title,
                "content": topic.content,
                "is_active": topic.is_active,
                "created_at": topic.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for topic in topics[:limit]
        ]
        
        return {
            "message": f"{len(topics_data)}個のお題を取得しました",
            "topics": topics_data
        }
    except Exception as e:
        logger.error(f"お題リスト取得エラー: {e}")
        return {"error": str(e)}