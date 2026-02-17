# app/analysis/fifth_force_ngram_generator.py
import random
import logging
import MeCab
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from .fifth_force_ngram_learner import FifthForceNgramLearner
from ..database.crud import DisplayWordCRUD

logger = logging.getLogger(__name__)


class FifthForceNgramGenerator:
    """第五の力用のn-gram生成器（品詞ベース、DBから単語取得）"""

    def __init__(self, learner: FifthForceNgramLearner, db: Session):
        self.learner = learner
        self.db = db
        self.tagger = MeCab.Tagger("")

        # DBから品詞別の単語をキャッシュ
        self._pos_cache = {}
        self._load_pos_cache()

    def _load_pos_cache(self):
        """DBから品詞別の単語をキャッシュ"""
        try:
            all_words = DisplayWordCRUD.get_all(self.db)

            # 品詞でグルーピング
            for word_obj in all_words:
                if word_obj.pos:
                    if word_obj.pos not in self._pos_cache:
                        self._pos_cache[word_obj.pos] = []
                    self._pos_cache[word_obj.pos].append(word_obj.word)

            logger.info(
                f"Fifth Force POS Cache: Loaded {len(all_words)} words across {len(self._pos_cache)} POS tags"
            )

        except Exception as e:
            logger.error(f"Error loading POS cache: {e}")

    def _get_word_for_pos(self, pos_tag: str) -> Optional[str]:
        """品詞タグから実際の単語を取得"""
        # 品詞タグから品詞を抽出（例: <名詞> -> 名詞）
        if pos_tag.startswith("<") and pos_tag.endswith(">"):
            pos = pos_tag[1:-1]

            # キャッシュから取得
            if pos in self._pos_cache and self._pos_cache[pos]:
                return random.choice(self._pos_cache[pos])

            logger.warning(f"No words found for POS: {pos}")
            return None

        # 品詞タグではない場合（機能語など）はそのまま返す
        return pos_tag

    def generate_from_words(
        self, words: List[str], count: int = 10, temperature: float = 0.8
    ) -> List[Dict[str, any]]:
        """
        与えられた単語からお題を生成（品詞ベース）

        Args:
            words: 開始単語の候補リスト
            count: 生成する個数
            temperature: サンプリング温度（0.5-1.5推奨）

        Returns:
            生成されたお題のリスト
        """
        generated_odais = []
        used_texts = set()
        used_start_words = set()

        logger.info(
            f"Fifth Force (n-gram POS): Starting generation with {len(words)} words, count={count}, temp={temperature}"
        )

        if not words:
            logger.warning("Fifth Force (n-gram POS): No words provided")
            return []

        if not self.learner.ngrams:
            logger.warning("Fifth Force (n-gram POS): No learned data available")
            return []

        attempts = 0
        max_attempts = count * 30

        while len(generated_odais) < count and attempts < max_attempts:
            attempts += 1

            # まだ使っていない単語を優先的に選択
            unused_words = [w for w in words if w not in used_start_words]
            if unused_words:
                start_word = random.choice(unused_words)
            else:
                start_word = random.choice(words)

            # お題を生成
            odai = self._generate_odai(start_word, temperature)

            if not odai:
                continue

            # 品質チェック
            if not self._is_quality_odai(odai, start_word):
                continue

            # 重複チェック
            if odai in used_texts:
                continue

            # 学習済みお題との重複チェック
            if odai in self.learner.learned_odais:
                continue

            # お題を追加
            quality_score = self._calculate_quality_score(odai)

            generated_odais.append(
                {
                    "text": odai,
                    "method": "fifth_force_ngram_pos",
                    "selected_word": start_word,
                    "quality_score": quality_score,
                }
            )
            used_texts.add(odai)
            used_start_words.add(start_word)

            logger.info(
                f"Fifth Force (n-gram POS): Generated: {odai} (word: {start_word}, score: {quality_score:.3f})"
            )

        logger.info(
            f"Fifth Force (n-gram POS): Generated {len(generated_odais)} odais in {attempts} attempts"
        )
        return generated_odais[:count]

    def _generate_odai(self, start_word: str, temperature: float = 0.8) -> Optional[str]:
        """指定された単語から開始してお題を生成（品詞ベース）"""
        max_length = 20  # 最大トークン数
        min_length = 3  # 最小トークン数

        # 開始単語の品詞を取得
        start_pos_tag = self._get_pos_tag_for_word(start_word)
        if not start_pos_tag:
            logger.warning(f"Could not determine POS for start word: {start_word}")
            return None

        # 初期状態を設定
        # n-1個の<START>トークンで開始
        prefix = ["<START>"] * (self.learner.n - 1)
        generated_tokens = [start_pos_tag]  # 品詞タグで開始
        prefix = prefix[1:] + [start_pos_tag]

        # トークンを生成
        for _ in range(max_length):
            prefix_tuple = tuple(prefix)

            # 次のトークン候補を取得
            candidates = self.learner.get_next_token_candidates(
                prefix_tuple, temperature
            )

            if not candidates:
                # 候補がない場合は終了
                break

            # 確率に基づいて次のトークンを選択
            next_token = self._sample_from_candidates(candidates)

            # 終了マーカーに到達したら終了
            if next_token == "<END>":
                if len(generated_tokens) >= min_length:
                    break
                else:
                    # 短すぎる場合は別の候補を試す
                    candidates_without_end = [
                        (t, p) for t, p in candidates if t != "<END>"
                    ]
                    if candidates_without_end:
                        next_token = self._sample_from_candidates(candidates_without_end)
                    else:
                        break

            generated_tokens.append(next_token)
            prefix = prefix[1:] + [next_token]

            # 長さ制限チェック
            if len(generated_tokens) >= max_length:
                break

        # 最小長チェック
        if len(generated_tokens) < min_length:
            return None

        # トークンを実際の単語に変換
        generated_words = []
        generated_words.append(start_word)  # 最初の単語は指定されたものを使用

        for token in generated_tokens[1:]:  # 2番目以降のトークンを変換
            word = self._get_word_for_pos(token)
            if word:
                generated_words.append(word)
            else:
                # 単語が見つからない場合は生成失敗
                return None

        # 単語を結合
        odai = "".join(generated_words)

        return odai

    def _get_pos_tag_for_word(self, word: str) -> Optional[str]:
        """単語から品詞タグを取得"""
        try:
            node = self.tagger.parseToNode(word)

            while node:
                if node.surface == word:
                    features = node.feature.split(",")
                    pos = features[0] if len(features) > 0 else ""

                    # 内容語なら品詞タグに
                    if pos in self.learner.CONTENT_POS:
                        return f"<{pos}>"
                    # 機能語ならそのまま
                    else:
                        return word

                node = node.next

        except Exception as e:
            logger.error(f"Error getting POS tag for word '{word}': {e}")

        return None

    def _sample_from_candidates(
        self, candidates: List[Tuple[str, float]]
    ) -> Optional[str]:
        """確率に基づいて候補から単語をサンプリング"""
        if not candidates:
            return None

        words, probs = zip(*candidates)

        # 確率に基づいてサンプリング
        try:
            selected = random.choices(words, weights=probs, k=1)[0]
            return selected
        except Exception as e:
            logger.error(f"Sampling error: {e}")
            return random.choice(words)

    def _is_quality_odai(self, odai: str, start_word: str) -> bool:
        """お題の品質チェック"""
        # 長さチェック
        if len(odai) < 5 or len(odai) > 50:
            return False

        # 開始単語が含まれているかチェック
        if start_word not in odai:
            return False

        # 繰り返しパターンのチェック（同じ単語が3回以上連続）
        words = self.learner._parse_to_words(odai)
        for i in range(len(words) - 2):
            if words[i] == words[i + 1] == words[i + 2]:
                return False

        # <START>や<END>が残っていないかチェック
        if "<START>" in odai or "<END>" in odai:
            return False

        return True

    def _calculate_quality_score(self, odai: str) -> float:
        """お題の品質スコアを計算"""
        score = 0.5  # ベーススコア

        # 長さによるスコア（10-20文字が理想）
        length = len(odai)
        if 10 <= length <= 20:
            score += 0.2
        elif 8 <= length <= 25:
            score += 0.1

        # 単語数によるスコア（3-8単語が理想）
        words = self.learner._parse_to_words(odai)
        word_count = len(words)
        if 3 <= word_count <= 8:
            score += 0.2
        elif 2 <= word_count <= 10:
            score += 0.1

        # DBに存在する単語の使用率
        db_words = sum(1 for w in words if any(w in word_list for word_list in self._pos_cache.values()))
        if word_count > 0:
            db_ratio = db_words / word_count
            score += db_ratio * 0.1

        return min(1.0, score)

    def get_generation_stats(self) -> Dict:
        """生成統計を取得"""
        return {
            "n": self.learner.n,
            "vocabulary_size": len(self.learner.token_freq),
            "total_patterns": len(self.learner.ngrams),
            "pos_cache_size": len(self._pos_cache),
        }
