from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.crud import DatabaseStatusCRUD
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"]
)

@router.get("/database-status")
async def get_database_status(db: Session = Depends(get_db)):
    """データベース状況確認"""
    try:
        status, details = DatabaseStatusCRUD.check_database_status(db)
        
        tables_info = {
            "news_articles": {"name": "ニュース記事", "count": 0, "status": ""},
            "extracted_words": {"name": "抽出単語", "count": 0, "status": ""},
            "ogiri_topics": {"name": "大喜利お題", "count": 0, "status": ""},
            "training_topics": {"name": "学習用お題", "count": 0, "status": ""}
        }
        
        # 実際のテーブル情報で更新
        for table_name, info in details.items():
            if table_name in tables_info:
                tables_info[table_name].update({
                    "count": info["count"],
                    "status": info["status"],
                    "exists": info["exists"]
                })
        
        return {
            "overall_status": status,
            "tables": tables_info,
            "summary": {
                "total_articles": tables_info["news_articles"]["count"],
                "total_words": tables_info["extracted_words"]["count"],
                "total_topics": tables_info["ogiri_topics"]["count"] + tables_info["training_topics"]["count"]
            }
        }
    except Exception as e:
        logger.error(f"データベース状態確認エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/repair-database")
async def repair_database(db: Session = Depends(get_db)):
    """データベースの修復（テーブルの再作成）"""
    try:
        status, result = DatabaseStatusCRUD.repair_database(db)
        if status == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"データベース修復エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"データベース修復エラー: {str(e)}"
        )