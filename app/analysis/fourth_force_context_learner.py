# app/analysis/fourth_force_context_learner.py
import json
import logging
import re
from typing import List, Dict, Tuple
from collections import defaultdict
import MeCab

logger = logging.getLogger(__name__)


class FourthForceContextLearner:
    """第四勢力用の文脈N-gram学習クラス"""

    def __init__(self):
        try:
            self.tagger = MeCab.Tagger("")
            logger.info("FourthForceContextLearner initialized successfully")
        except Exception as e:
            logger.error(f"MeCab initialization error: {e}")
            raise RuntimeError(f"Failed to initialize MeCab: {e}")

        # 学習データ
        self.context_patterns = defaultdict(
            lambda: defaultdict(lambda: {"count": 0, "examples": []})
        )  # 単語: 文脈パターン
        self.word_co_occurrences = defaultdict(int)  # 単語ペアの共起頻度
        self.templates = []  # テンプレート

        # 単語情報を格納
        self.word_info = defaultdict(lambda: {"pos": "", "examples": []})

    def learn_from_odai(self, odai_text: str) -> bool:
        """お題から文脈パターンを学習"""
        if not odai_text or not odai_text.strip():
            return False

        odai_text = odai_text.strip()

        # 品質チェック
        if not self._is_valid_odai(odai_text):
            return False

        try:
            # 形態素解析
            words = self._parse_text(odai_text)

            if not words:
                return False

            # 名詞を抽出
            nouns = [w for w in words if w["pos"] in ["名詞"]]

            if not nouns:
                return False

            # 各名詞について、その周辺の文脈（助詞、助動詞、動詞等）を学習
            for i, noun in enumerate(nouns):
                noun_word = noun["surface"]

                # 文脈パターンを抽出（前後2語）
                context = self._extract_context(words, noun, window=2)

                # 学習データに追加
                for context_word, context_pos in context:
                    pattern_key = f"{context_pos}"

                    self.context_patterns[noun_word][pattern_key]["count"] += 1

                    # 例文を保存（最大5個）
                    if (
                        len(self.context_patterns[noun_word][pattern_key]["examples"])
                        < 5
                    ):
                        self.context_patterns[noun_word][pattern_key][
                            "examples"
                        ].append(odai_text)

                # 単語情報を保存
                if (
                    noun_word not in self.word_info
                    or not self.word_info[noun_word]["pos"]
                ):
                    self.word_info[noun_word]["pos"] = noun["pos"]

                if len(self.word_info[noun_word]["examples"]) < 10:
                    self.word_info[noun_word]["examples"].append(odai_text)

            # テンプレート学習（名詞部分を{word}に置き換え）
            template = self._create_template(odai_text, nouns)
            if template and template not in self.templates:
                self.templates.append(template)
                # テンプレートは最大200個まで
                if len(self.templates) > 200:
                    self.templates.pop(0)

            logger.info(f"Fourth Force: Learned context from: {odai_text}")
            return True

        except Exception as e:
            logger.error(f"Error learning from odai '{odai_text}': {e}")
            return False

    def _parse_text(self, text: str) -> List[Dict]:
        """テキストを形態素解析"""
        words = []
        try:
            node = self.tagger.parseToNode(text)

            while node:
                if node.surface:
                    features = node.feature.split(",")
                    # 固有名詞を判定（"名詞,固有名詞"の場合）
                    pos = features[0] if len(features) > 0 else ""
                    if len(features) > 1:
                        # 第2カテゴリが「固有名詞」の場合はそれを含めて保存
                        if features[1] == "固有名詞":
                            pos = f"{pos},{features[1]}"

                    word_info = {
                        "surface": node.surface,
                        "base_form": features[6] if len(features) > 6 else node.surface,
                        "pos": pos,
                        "inflection": features[5]
                        if len(features) > 5
                        else "",  # 活用形
                        "pos_detail": features[1]
                        if len(features) > 1
                        else "",  # 品詞細分類
                    }
                    words.append(word_info)
                node = node.next
        except Exception as e:
            logger.error(f"Parsing error: {e}")

        return words

    def _extract_context(
        self, words: List[Dict], target_word: Dict, window: int = 2
    ) -> List[Tuple[str, str]]:
        """単語の周辺文脈を抽出"""
        context = []

        try:
            target_idx = -1
            for i, word in enumerate(words):
                if word["surface"] == target_word["surface"]:
                    target_idx = i
                    break

            if target_idx == -1:
                return context

            # 前後の文脈を取得
            for i in range(
                max(0, target_idx - window), min(len(words), target_idx + window + 1)
            ):
                if i != target_idx:
                    word = words[i]
                    context.append((word["surface"], word["pos"]))

        except Exception as e:
            logger.error(f"Context extraction error: {e}")

        return context

    def _create_template(self, odai_text: str, nouns: List[Dict]) -> str:
        """テンプレートを作成（最初の名詞を{word}に置き換え）"""
        if not nouns:
            return None

        # 最初の名詞のみ置き換え
        template = odai_text
        first_noun = nouns[0]["surface"]

        # 最初に出現する位置で置き換え
        template = template.replace(first_noun, "{word}", 1)

        # テンプレートらしくなっているかチェック
        if "{word}" in template:
            return template

        return None

    def _is_valid_odai(self, odai_text: str) -> bool:
        """お題の品質チェック"""
        if not odai_text:
            return False

        # 長さチェック
        if len(odai_text) < 3 or len(odai_text) > 30:
            return False

        # 既存のテンプレートと重複チェック
        if odai_text in self.templates:
            return False

        return True

    def get_context_for_word(self, word: str) -> List[Tuple[str, int]]:
        """単語の文脈パターンを取得"""
        if word not in self.context_patterns:
            return []

        # カウント順でソート
        patterns = []
        for pattern_key, data in self.context_patterns[word].items():
            patterns.append((pattern_key, data.get("count", 0)))

        patterns.sort(key=lambda x: x[1], reverse=True)
        return patterns

    def get_similar_context(self, target_word: str, candidate_words: List[str]) -> str:
        """類似の文脈を持つ単語を見つける"""
        if target_word not in self.context_patterns:
            return None

        target_patterns = set(self.context_patterns[target_word].keys())

        best_match = None
        best_score = 0

        for word in candidate_words:
            if word not in self.context_patterns:
                continue

            word_patterns = set(self.context_patterns[word].keys())

            # パターンの類似度を計算
            intersection = target_patterns & word_patterns
            union = target_patterns | word_patterns

            if len(union) > 0:
                score = len(intersection) / len(union)
                if score > best_score:
                    best_score = score
                    best_match = word

        return best_match

    def get_learning_stats(self) -> Dict:
        """学習統計を取得"""
        return {
            "learned_words": len(self.context_patterns),
            "templates": len(self.templates),
            "word_info_count": len(self.word_info),
        }

    def save_learning_data(self, file_path: str):
        """学習データを保存"""
        data = {
            "context_patterns": {k: dict(v) for k, v in self.context_patterns.items()},
            "templates": self.templates,
            "word_info": dict(self.word_info),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Fourth Force learning data saved to {file_path}")

    def load_learning_data(self, file_path: str):
        """学習データを読み込み"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.context_patterns = defaultdict(
                lambda: defaultdict(lambda: {"count": 0, "examples": []}),
                {
                    k: defaultdict(lambda: {"count": 0, "examples": []}, v)
                    for k, v in data.get("context_patterns", {}).items()
                },
            )
            self.templates = data.get("templates", [])
            self.word_info = defaultdict(
                lambda: {"pos": "", "examples": []}, data.get("word_info", {})
            )

            logger.info(f"Fourth Force learning data loaded from {file_path}")

        except FileNotFoundError:
            logger.info(f"Fourth Force learning data file not found: {file_path}")
        except Exception as e:
            logger.error(f"Error loading Fourth Force learning data: {e}")

    def reset(self):
        """学習データをリセット"""
        self.context_patterns = defaultdict(
            lambda: defaultdict(lambda: {"count": 0, "examples": []})
        )
        self.templates = []
        self.word_info = defaultdict(lambda: {"pos": "", "examples": []})
        logger.info("Fourth Force learning data reset")
