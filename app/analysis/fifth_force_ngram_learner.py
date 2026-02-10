# app/analysis/fifth_force_ngram_learner.py
import json
import logging
import random
from typing import List, Dict, Tuple
from collections import defaultdict, Counter
import MeCab

logger = logging.getLogger(__name__)


class FifthForceNgramLearner:
    """第五の力用のn-gram学習クラス（品詞ベース）"""

    # 内容語として扱う品詞（品詞タグに置き換える）
    CONTENT_POS = {"名詞", "動詞", "形容詞", "副詞", "形容動詞", "連体詞"}

    # 機能語として扱う品詞（そのまま保持）
    FUNCTION_POS = {"助詞", "助動詞", "接続詞", "感動詞"}

    def __init__(self, n: int = 3):
        """
        Args:
            n: n-gramのサイズ（デフォルト3-gram）
        """
        self.n = n
        try:
            self.tagger = MeCab.Tagger("")
            logger.info(f"FifthForceNgramLearner initialized (n={n}, POS-based)")
        except Exception as e:
            logger.error(f"MeCab initialization error: {e}")
            raise RuntimeError(f"Failed to initialize MeCab: {e}")

        # n-gram統計（品詞パターンベース）
        self.ngrams = defaultdict(Counter)  # (token1, token2, ..., tokenn-1) -> Counter({tokenn: count})
        self.token_freq = Counter()  # トークン頻度
        self.start_tokens = Counter()  # 開始トークンの頻度
        self.end_patterns = []  # 終了パターン（文末の数トークン）

        # 学習データ
        self.learned_odais = []  # 学習したお題のリスト（最大500個）

    def learn_from_odai(self, odai_text: str) -> bool:
        """お題からn-gramを学習（品詞パターンベース）"""
        if not odai_text or not odai_text.strip():
            return False

        odai_text = odai_text.strip()

        # 品質チェック
        if len(odai_text) < 3 or len(odai_text) > 50:
            return False

        try:
            # 形態素解析してトークン化（品詞タグ化）
            tokens = self._parse_to_tokens(odai_text)

            if len(tokens) < 2:
                return False

            # 開始マーカーと終了マーカーを追加
            tokens_with_markers = ["<START>"] * (self.n - 1) + tokens + ["<END>"]

            # n-gramを抽出
            for i in range(len(tokens_with_markers) - self.n + 1):
                ngram = tuple(tokens_with_markers[i : i + self.n])
                prefix = ngram[:-1]
                next_token = ngram[-1]

                self.ngrams[prefix][next_token] += 1

            # トークン頻度を更新
            for token in tokens:
                self.token_freq[token] += 1

            # 開始トークンを記録
            if tokens:
                self.start_tokens[tokens[0]] += 1

            # 終了パターンを記録（最後の2-3トークン）
            if len(tokens) >= 2:
                end_pattern = tuple(tokens[-2:])
                self.end_patterns.append(end_pattern)
                if len(self.end_patterns) > 100:
                    self.end_patterns.pop(0)

            # 学習したお題を保存
            if odai_text not in self.learned_odais:
                self.learned_odais.append(odai_text)
                if len(self.learned_odais) > 500:
                    self.learned_odais.pop(0)

            logger.info(f"Fifth Force (n-gram POS): Learned from: {odai_text} -> {tokens}")
            return True

        except Exception as e:
            logger.error(f"Error learning from odai '{odai_text}': {e}")
            return False

    def _parse_to_tokens(self, text: str) -> List[str]:
        """
        テキストを品詞ベースのトークンリストに分割
        内容語は品詞タグに、機能語はそのまま保持
        """
        tokens = []
        try:
            node = self.tagger.parseToNode(text)

            while node:
                if node.surface:
                    features = node.feature.split(",")
                    pos = features[0] if len(features) > 0 else ""

                    # 記号以外を抽出
                    if pos not in ["記号", "BOS/EOS"]:
                        # 内容語は品詞タグに置き換え
                        if pos in self.CONTENT_POS:
                            token = f"<{pos}>"
                        # 機能語はそのまま
                        elif pos in self.FUNCTION_POS:
                            token = node.surface
                        # その他（接頭辞、接尾辞など）もそのまま
                        else:
                            token = node.surface

                        tokens.append(token)

                node = node.next

        except Exception as e:
            logger.error(f"Parsing error: {e}")

        return tokens

    def _parse_to_words(self, text: str) -> List[str]:
        """テキストを単語リストに分割（品質チェック用に残す）"""
        words = []
        try:
            node = self.tagger.parseToNode(text)

            while node:
                if node.surface:
                    # 記号類は除外
                    features = node.feature.split(",")
                    pos = features[0] if len(features) > 0 else ""

                    # 記号以外を抽出
                    if pos not in ["記号", "BOS/EOS"]:
                        words.append(node.surface)

                node = node.next

        except Exception as e:
            logger.error(f"Parsing error: {e}")

        return words

    def get_next_token_candidates(
        self, prefix: Tuple[str, ...], temperature: float = 1.0
    ) -> List[Tuple[str, float]]:
        """
        前のトークン列から次のトークンの候補を確率とともに取得

        Args:
            prefix: 前の(n-1)個のトークンのタプル
            temperature: サンプリング温度（1.0=通常、低い=保守的、高い=多様）

        Returns:
            [(トークン, 確率), ...] のリスト
        """
        if prefix not in self.ngrams:
            return []

        counter = self.ngrams[prefix]
        total = sum(counter.values())

        if total == 0:
            return []

        # 確率を計算（temperatureを適用）
        candidates = []
        for token, count in counter.items():
            prob = count / total
            # Temperature適用
            adjusted_prob = prob ** (1.0 / temperature)
            candidates.append((token, adjusted_prob))

        # 正規化
        total_prob = sum(prob for _, prob in candidates)
        if total_prob > 0:
            candidates = [(token, prob / total_prob) for token, prob in candidates]

        # 確率順にソート
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates

    def get_learning_stats(self) -> Dict:
        """学習統計を取得"""
        return {
            "n": self.n,
            "total_ngrams": len(self.ngrams),
            "vocabulary_size": len(self.token_freq),
            "learned_odais": len(self.learned_odais),
            "start_tokens": len(self.start_tokens),
        }

    def save_learning_data(self, file_path: str):
        """学習データを保存"""
        # defaultdictとCounterをJSON化
        data = {
            "n": self.n,
            "ngrams": {
                "|".join(k): dict(v) for k, v in self.ngrams.items()
            },
            "token_freq": dict(self.token_freq),
            "start_tokens": dict(self.start_tokens),
            "end_patterns": [list(p) for p in self.end_patterns],
            "learned_odais": self.learned_odais,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Fifth Force (n-gram POS) learning data saved to {file_path}")

    def load_learning_data(self, file_path: str):
        """学習データを読み込み"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.n = data.get("n", 3)

            # ngramsを復元
            self.ngrams = defaultdict(Counter)
            for k, v in data.get("ngrams", {}).items():
                key = tuple(k.split("|"))
                self.ngrams[key] = Counter(v)

            self.token_freq = Counter(data.get("token_freq", {}))
            self.start_tokens = Counter(data.get("start_tokens", {}))
            self.end_patterns = [tuple(p) for p in data.get("end_patterns", [])]
            self.learned_odais = data.get("learned_odais", [])

            logger.info(f"Fifth Force (n-gram POS) learning data loaded from {file_path}")

        except FileNotFoundError:
            logger.info(f"Fifth Force (n-gram POS) learning data file not found: {file_path}")
        except Exception as e:
            logger.error(f"Error loading Fifth Force (n-gram POS) learning data: {e}")

    def reset(self):
        """学習データをリセット"""
        self.ngrams = defaultdict(Counter)
        self.token_freq = Counter()
        self.start_tokens = Counter()
        self.end_patterns = []
        self.learned_odais = []
        logger.info("Fifth Force (n-gram POS) learning data reset")
