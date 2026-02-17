# app/database/connection.py - 修正版（ディレクトリ作成対応）
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

# データベースファイルのパス設定
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DATABASE_FILE = os.path.join(DATABASE_DIR, "app.db")

# データベースディレクトリが存在しない場合は作成
os.makedirs(DATABASE_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        # display_words.pos が無ければ追加
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pragma_table_info('display_words') WHERE name='pos'")
            ).first()
            if not exists:
                conn.execute(text("ALTER TABLE display_words ADD COLUMN pos VARCHAR(50)"))
        logger.info("データベーステーブルを作成しました")
    except Exception as e:
        logger.error(f"データベース初期化エラー: {e}")
        raise