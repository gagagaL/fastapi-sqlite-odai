#!/usr/bin/env python3
"""確定お題から第五の力を学習するスクリプト"""

from app.database.connection import get_db
from app.database.crud import ConfirmedOdaiCRUD
from app.analysis.fifth_force_ngram_learner import FifthForceNgramLearner

# 第五の力の学習データパス
FIFTH_FORCE_DATA_PATH = "app/data/fifth_force_ngram_learning_data.json"


def main():
    # DBセッションを取得
    db = next(get_db())

    try:
        # 第五の力の学習器を作成
        learner = FifthForceNgramLearner(n=3)

        # 確定お題を取得
        confirmed_odais = ConfirmedOdaiCRUD.get_all(db, limit=10000)

        print(f"確定お題を {len(confirmed_odais)} 個取得しました")

        # 各お題から学習
        learned_count = 0
        for odai in confirmed_odais:
            if learner.learn_from_odai(odai.odai_text):
                learned_count += 1

        print(f"{learned_count} 個のお題から学習しました")

        # 学習データを保存
        learner.save_learning_data(FIFTH_FORCE_DATA_PATH)
        print(f"学習データを {FIFTH_FORCE_DATA_PATH} に保存しました")

        # 統計を表示
        stats = learner.get_learning_stats()
        print("\n学習統計:")
        print(f"  - n-gramサイズ: {stats['n']}")
        print(f"  - パターン数: {stats['total_ngrams']}")
        print(f"  - 語彙サイズ: {stats['vocabulary_size']}")
        print(f"  - 学習済みお題数: {stats['learned_odais']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
