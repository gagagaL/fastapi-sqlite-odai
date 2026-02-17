#!/usr/bin/env python3
"""第五の力の生成をテストするスクリプト"""

from app.database.connection import get_db
from app.database.crud import DisplayWordCRUD
from app.analysis.fifth_force_ngram_learner import FifthForceNgramLearner
from app.analysis.fifth_force_ngram_generator import FifthForceNgramGenerator

# 第五の力の学習データパス
FIFTH_FORCE_DATA_PATH = "app/data/fifth_force_ngram_learning_data.json"


def main():
    # DBセッションを取得
    db = next(get_db())

    try:
        # 第五の力の学習器を作成
        learner = FifthForceNgramLearner(n=3)
        learner.load_learning_data(FIFTH_FORCE_DATA_PATH)

        # 統計を表示
        stats = learner.get_learning_stats()
        print("学習統計:")
        print(f"  - n-gramサイズ: {stats['n']}")
        print(f"  - パターン数: {stats['total_ngrams']}")
        print(f"  - 語彙サイズ: {stats['vocabulary_size']}")
        print(f"  - 学習済みお題数: {stats['learned_odais']}")
        print()

        # 生成器を作成
        generator = FifthForceNgramGenerator(learner, db)

        # 開始単語を取得
        words = DisplayWordCRUD.get_all(db)
        words_to_use = [word.word for word in words if word.word]

        print(f"開始単語候補: {len(words_to_use)}個")
        print(f"例: {', '.join(words_to_use[:10])}")
        print()

        # お題を生成
        print("お題を生成中...")
        generated_odais = generator.generate_from_words(
            words_to_use, count=5, temperature=0.8
        )

        print(f"\n生成されたお題（{len(generated_odais)}個）:")
        for i, odai in enumerate(generated_odais, 1):
            print(f"  {i}. {odai['text']}")
            print(f"     - 開始単語: {odai['selected_word']}")
            print(f"     - 品質スコア: {odai['quality_score']:.3f}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
