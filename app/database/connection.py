# app/database/connection.py - 修正版（ディレクトリ作成対応）
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import sessionmaker
from ..config import get_settings
import os

settings = get_settings()

# データベースファイルのパス
database_path = "./data/database/app.db"
database_dir = os.path.dirname(database_path)

# データベースディレクトリを作成
os.makedirs("data/database", exist_ok=True)

# SQLiteエンジン作成
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}  # SQLite用設定
)

# データベースディレクトリを確実に作成
try:
    os.makedirs(database_dir, exist_ok=True)
    print(f"✅ データベースディレクトリを作成: {database_dir}")
except OSError as e:
    print(f"⚠️ ディレクトリ作成エラー: {e}")
    # フォールバック: 現在のディレクトリにDBファイル作成
    database_path = "./app.db"
    print(f"📁 フォールバック: {database_path} を使用")



# セッション作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ベースクラス
Base = declarative_base()

def get_db():
    """データベースセッションの依存関係注入用"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    """データベース初期化"""
    try:
        # データベースファイルの親ディレクトリを再確認
        db_file_path = database_path
        db_dir = os.path.dirname(os.path.abspath(db_file_path))
        
        print(f"📁 データベースディレクトリ確認: {db_dir}")
        print(f"📝 データベースファイル: {db_file_path}")
        
        # ディレクトリ存在確認
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"✅ ディレクトリを作成しました: {db_dir}")
        
        # 権限確認
        if not os.access(db_dir, os.W_OK):
            print(f"⚠️ 書き込み権限がありません: {db_dir}")
            # 権限修正を試行
            try:
                os.chmod(db_dir, 0o755)
                print(f"✅ 権限を修正しました: {db_dir}")
            except Exception as e:
                print(f"❌ 権限修正失敗: {e}")
        
        # テーブル作成
        Base.metadata.create_all(bind=engine)
        print("✅ データベーステーブルを初期化しました")
        
        # 接続テスト
        with engine.connect() as conn:
            print("✅ データベース接続テスト成功")
            
    except Exception as e:
        print(f"❌ データベース初期化エラー: {e}")
        print(f"📊 現在の作業ディレクトリ: {os.getcwd()}")
        print(f"📁 ディレクトリ内容: {os.listdir('.')}")
        
        # 緊急フォールバック: メモリ内SQLite
        # global engine, SessionLocal
        # print("🚨 緊急フォールバック: メモリ内SQLite使用")
        # engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        # SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        # Base.metadata.create_all(bind=engine)
        # print("✅ メモリ内データベースで初期化完了")