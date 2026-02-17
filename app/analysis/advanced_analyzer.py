# app/analysis/advanced_analyzer.py
import logging
from typing import List, Dict, Optional, Tuple
import random
import re

# 複数の形態素解析器を試行
try:
    from sudachipy import tokenizer
    from sudachipy import dictionary

    SUDACHI_AVAILABLE = True
except ImportError:
    SUDACHI_AVAILABLE = False

try:
    from janome.tokenizer import Tokenizer

    JANOME_AVAILABLE = True
except ImportError:
    JANOME_AVAILABLE = False

logger = logging.getLogger(__name__)


class AdvancedAnalyzer:
    """複数の形態素解析器を活用した高度な文書分析"""

    def __init__(self, verb_processor):
        self.verb_processor = verb_processor
        self.sudachi_available = SUDACHI_AVAILABLE
        self.janome_available = JANOME_AVAILABLE

        # SudachiPyの初期化
        if self.sudachi_available:
            try:
                self.sudachi_tokenizer = dictionary.Dictionary().create()
                self.sudachi_mode = tokenizer.Tokenizer.SplitMode.C
            except Exception as e:
                logger.warning(f"SudachiPy initialization failed: {e}")
                self.sudachi_available = False

        # Janomeの初期化
        if self.janome_available:
            try:
                self.janome_tokenizer = Tokenizer()
            except Exception as e:
                logger.warning(f"Janome initialization failed: {e}")
                self.janome_available = False

    def analyze_odai_quality(self, text: str) -> Dict[str, float]:
        """お題の品質を高度に分析"""
        if not text:
            return {"overall_score": 0.0}

        # 複数の解析器で分析
        analyses = []

        # SudachiPy分析
        if self.sudachi_available:
            sudachi_analysis = self._analyze_with_sudachi(text)
            if sudachi_analysis:
                analyses.append(sudachi_analysis)

        # Janome分析
        if self.janome_available:
            janome_analysis = self._analyze_with_janome(text)
            if janome_analysis:
                analyses.append(janome_analysis)

        # MeCab分析（フォールバック）
        mecab_analysis = self._analyze_with_mecab(text)
        if mecab_analysis:
            analyses.append(mecab_analysis)

        if not analyses:
            return {"overall_score": 0.0}

        # 複数解析器の結果を統合
        return self._integrate_analyses(analyses)

    def _analyze_with_sudachi(self, text: str) -> Optional[Dict[str, float]]:
        """SudachiPyで分析"""
        try:
            tokens = self.sudachi_tokenizer.tokenize(text, self.sudachi_mode)

            # 品詞の詳細分析
            pos_details = []
            word_forms = []
            reading_forms = []

            for token in tokens:
                pos_details.append(token.part_of_speech())
                word_forms.append(token.surface())
                reading_forms.append(token.reading_form())

            # 細かい品詞分類
            detailed_pos = [pos[0] for pos in pos_details]
            sub_pos = [pos[1] for pos in pos_details if len(pos) > 1]

            scores = {
                "syntactic_complexity": self._calculate_sudachi_syntactic_complexity(
                    tokens, text
                ),
                "semantic_richness": self._calculate_sudachi_semantic_richness(tokens),
                "odai_likeness": self._calculate_odai_likeness_advanced(
                    text, word_forms, detailed_pos
                ),
                "grammatical_correctness": self._calculate_sudachi_grammatical_correctness(
                    tokens
                ),
                "creativity_potential": self._calculate_creativity_potential_advanced(
                    text, word_forms
                ),
                "reading_diversity": self._calculate_reading_diversity(reading_forms),
                "pos_granularity": self._calculate_pos_granularity(
                    detailed_pos, sub_pos
                ),
            }

            return scores

        except Exception as e:
            logger.warning(f"SudachiPy analysis failed: {e}")
            return None

    def _analyze_with_janome(self, text: str) -> Optional[Dict[str, float]]:
        """Janomeで分析"""
        try:
            tokens = list(self.janome_tokenizer.tokenize(text))

            # 品詞の詳細分析
            pos_details = [token.part_of_speech for token in tokens]
            word_forms = [token.surface for token in tokens]
            base_forms = [token.base_form for token in tokens]

            scores = {
                "syntactic_complexity": self._calculate_janome_syntactic_complexity(
                    tokens, text
                ),
                "semantic_richness": self._calculate_janome_semantic_richness(tokens),
                "odai_likeness": self._calculate_odai_likeness_advanced(
                    text, word_forms, pos_details
                ),
                "grammatical_correctness": self._calculate_janome_grammatical_correctness(
                    tokens
                ),
                "creativity_potential": self._calculate_creativity_potential_advanced(
                    text, word_forms
                ),
                "base_form_diversity": self._calculate_base_form_diversity(base_forms),
                "inflection_richness": self._calculate_inflection_richness(tokens),
            }

            return scores

        except Exception as e:
            logger.warning(f"Janome analysis failed: {e}")
            return None

    def _analyze_with_mecab(self, text: str) -> Optional[Dict[str, float]]:
        """MeCabで分析（フォールバック）"""
        try:
            words = self.verb_processor.extract_all_word_forms(text)
            if not words:
                return None

            pos_details = [word["pos"] for word in words]
            word_forms = [word["surface"] for word in words]

            scores = {
                "syntactic_complexity": self._calculate_mecab_syntactic_complexity(
                    words, text
                ),
                "semantic_richness": self._calculate_mecab_semantic_richness(words),
                "odai_likeness": self._calculate_odai_likeness_advanced(
                    text, word_forms, pos_details
                ),
                "grammatical_correctness": self._calculate_mecab_grammatical_correctness(
                    words, text
                ),
                "creativity_potential": self._calculate_creativity_potential_advanced(
                    text, word_forms
                ),
            }

            return scores

        except Exception as e:
            logger.warning(f"MeCab analysis failed: {e}")
            return None

    def _integrate_analyses(self, analyses: List[Dict[str, float]]) -> Dict[str, float]:
        """複数解析器の結果を統合"""
        if not analyses:
            return {"overall_score": 0.0}

        # 重み付き平均（SudachiPy > Janome > MeCab）
        weights = [0.5, 0.3, 0.2][: len(analyses)]
        total_weight = sum(weights)

        integrated_scores = {}
        for key in analyses[0].keys():
            weighted_sum = sum(
                analysis.get(key, 0) * weight
                for analysis, weight in zip(analyses, weights)
            )
            integrated_scores[key] = weighted_sum / total_weight

        # 総合スコアの計算（より細かい重み付け）
        score_weights = {
            "syntactic_complexity": 0.15,
            "semantic_richness": 0.20,
            "odai_likeness": 0.25,
            "grammatical_correctness": 0.15,
            "creativity_potential": 0.10,
            "reading_diversity": 0.05,
            "pos_granularity": 0.05,
            "base_form_diversity": 0.03,
            "inflection_richness": 0.02,
        }

        overall_score = sum(
            integrated_scores.get(key, 0) * weight
            for key, weight in score_weights.items()
        )

        integrated_scores["overall_score"] = overall_score
        return integrated_scores

    def _calculate_sudachi_syntactic_complexity(self, tokens, text: str) -> float:
        """SudachiPyによる構文複雑さ計算"""
        if not tokens:
            return 0.0

        # 文の長さ
        length_score = min(len(text) / 15, 1.0)

        # 品詞の多様性（細かい分類）
        pos_set = set(token.part_of_speech()[0] for token in tokens)
        diversity_score = min(len(pos_set) / 10, 1.0)

        # 語形変化の複雑さ
        inflection_score = 0.0
        for token in tokens:
            if len(token.part_of_speech()) > 2:  # 活用形情報がある場合
                inflection_score += 0.1
        inflection_score = min(inflection_score, 1.0)

        return (length_score + diversity_score + inflection_score) / 3

    def _calculate_sudachi_semantic_richness(self, tokens) -> float:
        """SudachiPyによる意味的豊富さ計算"""
        if not tokens:
            return 0.0

        # 内容語の割合
        content_words = 0
        for token in tokens:
            pos = token.part_of_speech()[0]
            if pos in ["名詞", "動詞", "形容詞", "副詞"]:
                content_words += 1

        content_ratio = content_words / len(tokens)

        # 固有表現の検出
        entity_score = 0.0
        for token in tokens:
            if token.part_of_speech()[0] == "名詞" and len(token.surface()) >= 2:
                entity_score += 0.1
        entity_score = min(entity_score, 1.0)

        return (content_ratio + entity_score) / 2

    def _calculate_janome_syntactic_complexity(self, tokens, text: str) -> float:
        """Janomeによる構文複雑さ計算"""
        if not tokens:
            return 0.0

        # 文の長さ
        length_score = min(len(text) / 15, 1.0)

        # 品詞の多様性
        pos_set = set(token.part_of_speech.split(",")[0] for token in tokens)
        diversity_score = min(len(pos_set) / 10, 1.0)

        # 活用形の複雑さ
        inflection_score = 0.0
        for token in tokens:
            if token.infl_type and token.infl_type != "*":
                inflection_score += 0.1
        inflection_score = min(inflection_score, 1.0)

        return (length_score + diversity_score + inflection_score) / 3

    def _calculate_janome_semantic_richness(self, tokens) -> float:
        """Janomeによる意味的豊富さ計算"""
        if not tokens:
            return 0.0

        # 内容語の割合
        content_words = 0
        for token in tokens:
            pos = token.part_of_speech.split(",")[0]
            if pos in ["名詞", "動詞", "形容詞", "副詞"]:
                content_words += 1

        content_ratio = content_words / len(tokens)

        # 基本形の多様性
        base_forms = [token.base_form for token in tokens if token.base_form != "*"]
        base_diversity = len(set(base_forms)) / len(base_forms) if base_forms else 0

        return (content_ratio + base_diversity) / 2

    def _calculate_odai_likeness_advanced(
        self, text: str, word_forms: List[str], pos_details: List[str]
    ) -> float:
        """高度なお題らしさ計算"""
        score = 0.0

        # 疑問詞の検出（より詳細）
        question_words = [
            "何",
            "誰",
            "どこ",
            "いつ",
            "なぜ",
            "どう",
            "どれ",
            "どの",
            "どんな",
            "どちら",
        ]
        if any(word in text for word in question_words):
            score += 0.3

        # 比較表現の検出（より詳細）
        comparison_words = [
            "より",
            "ほど",
            "くらい",
            "みたい",
            "ような",
            "らしい",
            "っぽい",
            "がち",
        ]
        if any(word in text for word in comparison_words):
            score += 0.2

        # 感情・評価表現の検出（より詳細）
        emotion_words = [
            "好き",
            "嫌い",
            "怖い",
            "楽しい",
            "面白い",
            "変",
            "不思議",
            "すごい",
            "やばい",
            "キモい",
        ]
        if any(word in text for word in emotion_words):
            score += 0.2

        # 対比構造の検出（より詳細）
        contrast_words = [
            "でも",
            "しかし",
            "一方",
            "逆に",
            "それなのに",
            "なのに",
            "のに",
        ]
        if any(word in text for word in contrast_words):
            score += 0.1

        # 短い文（お題らしさ）
        if len(text) <= 8:
            score += 0.2

        # 品詞パターンのお題らしさ
        if len(pos_details) >= 2:
            # 名詞+形容詞のパターン
            if "名詞" in pos_details and "形容詞" in pos_details:
                score += 0.1
            # 名詞+動詞のパターン
            if "名詞" in pos_details and "動詞" in pos_details:
                score += 0.1

        return min(score, 1.0)

    def _calculate_creativity_potential_advanced(
        self, text: str, word_forms: List[str]
    ) -> float:
        """高度な創造性の潜在力計算"""
        score = 0.0

        # 抽象的な概念（より詳細）
        abstract_words = [
            "秘密",
            "謎",
            "不思議",
            "驚き",
            "発見",
            "体験",
            "記憶",
            "夢",
            "希望",
            "未来",
            "過去",
        ]
        abstract_score = sum(1 for word in abstract_words if word in text) * 0.05
        score += abstract_score

        # 比喩表現（より詳細）
        metaphor_words = ["みたい", "ような", "まるで", "さながら", "っぽい", "らしい"]
        metaphor_score = sum(1 for word in metaphor_words if word in text) * 0.1
        score += metaphor_score

        # 意外性のある組み合わせ
        unexpected_combinations = [
            ("宇宙", "おばあさん"),
            ("時間", "止まる"),
            ("魔法", "科学"),
            ("未来", "過去"),
            ("現実", "夢"),
            ("人間", "ロボット"),
        ]
        for combo in unexpected_combinations:
            if all(word in text for word in combo):
                score += 0.2

        # 語彙の多様性
        unique_words = len(set(word_forms))
        total_words = len(word_forms)
        if total_words > 0:
            diversity_score = unique_words / total_words
            score += diversity_score * 0.1

        return min(score, 1.0)

    def _calculate_reading_diversity(self, reading_forms: List[str]) -> float:
        """読み方の多様性計算"""
        if not reading_forms:
            return 0.0

        unique_readings = len(set(reading_forms))
        total_readings = len(reading_forms)

        return unique_readings / total_readings if total_readings > 0 else 0.0

    def _calculate_pos_granularity(
        self, detailed_pos: List[str], sub_pos: List[str]
    ) -> float:
        """品詞の細かさ計算"""
        if not detailed_pos:
            return 0.0

        # 細かい品詞分類の多様性
        pos_diversity = len(set(detailed_pos)) / len(detailed_pos)
        sub_pos_diversity = len(set(sub_pos)) / len(sub_pos) if sub_pos else 0

        return (pos_diversity + sub_pos_diversity) / 2

    def _calculate_base_form_diversity(self, base_forms: List[str]) -> float:
        """基本形の多様性計算"""
        if not base_forms:
            return 0.0

        unique_forms = len(set(base_forms))
        total_forms = len(base_forms)

        return unique_forms / total_forms if total_forms > 0 else 0.0

    def _calculate_inflection_richness(self, tokens) -> float:
        """活用の豊富さ計算"""
        if not tokens:
            return 0.0

        inflection_count = 0
        for token in tokens:
            if (
                hasattr(token, "infl_type")
                and token.infl_type
                and token.infl_type != "*"
            ):
                inflection_count += 1

        return inflection_count / len(tokens) if tokens else 0.0

    def get_word_importance_scores(self, text: str) -> Dict[str, float]:
        """単語の重要度スコアを計算（複数解析器統合）"""
        if not text:
            return {}

        # 複数の解析器で単語を抽出
        all_words = set()

        # SudachiPy
        if self.sudachi_available:
            try:
                tokens = self.sudachi_tokenizer.tokenize(text, self.sudachi_mode)
                for token in tokens:
                    if token.part_of_speech()[0] not in ["助詞", "助動詞", "記号"]:
                        all_words.add(token.surface())
            except:
                pass

        # Janome
        if self.janome_available:
            try:
                tokens = list(self.janome_tokenizer.tokenize(text))
                for token in tokens:
                    pos = token.part_of_speech.split(",")[0]
                    if pos not in ["助詞", "助動詞", "記号"]:
                        all_words.add(token.surface)
            except:
                pass

        # MeCab（フォールバック）
        try:
            words = self.verb_processor.extract_all_word_forms(text)
            for word in words:
                if word["pos"] not in ["助詞", "助動詞", "記号"]:
                    all_words.add(word["surface"])
        except:
            pass

        # 重要度スコアを計算
        word_scores = {}
        for word in all_words:
            score = 0.0

            # 基本的な重み付け
            if len(word) >= 2:
                score += 0.1

            # 品詞による重み付け（複数解析器の結果を統合）
            pos_scores = self._get_pos_scores_for_word(word, text)
            score += pos_scores

            # 文脈による重み付け
            context_score = self._calculate_context_score(word, text)
            score += context_score

            word_scores[word] = score

        return word_scores

    def _get_pos_scores_for_word(self, word: str, text: str) -> float:
        """単語の品詞スコアを複数解析器で計算"""
        max_score = 0.0

        # SudachiPy
        if self.sudachi_available:
            try:
                tokens = self.sudachi_tokenizer.tokenize(text, self.sudachi_mode)
                for token in tokens:
                    if token.surface() == word:
                        pos = token.part_of_speech()[0]
                        if pos == "名詞":
                            max_score = max(max_score, 0.4)
                        elif pos == "動詞":
                            max_score = max(max_score, 0.3)
                        elif pos == "形容詞":
                            max_score = max(max_score, 0.2)
                        elif pos == "副詞":
                            max_score = max(max_score, 0.1)
            except:
                pass

        # Janome
        if self.janome_available:
            try:
                tokens = list(self.janome_tokenizer.tokenize(text))
                for token in tokens:
                    if token.surface == word:
                        pos = token.part_of_speech.split(",")[0]
                        if pos == "名詞":
                            max_score = max(max_score, 0.4)
                        elif pos == "動詞":
                            max_score = max(max_score, 0.3)
                        elif pos == "形容詞":
                            max_score = max(max_score, 0.2)
                        elif pos == "副詞":
                            max_score = max(max_score, 0.1)
            except:
                pass

        # MeCab（フォールバック）
        try:
            words = self.verb_processor.extract_all_word_forms(text)
            for word_info in words:
                if word_info["surface"] == word:
                    pos = word_info["pos"]
                    if pos == "名詞":
                        max_score = max(max_score, 0.4)
                    elif pos == "動詞":
                        max_score = max(max_score, 0.3)
                    elif pos == "形容詞":
                        max_score = max(max_score, 0.2)
                    elif pos == "副詞":
                        max_score = max(max_score, 0.1)
        except:
            pass

        return max_score

    def _calculate_context_score(self, word: str, text: str) -> float:
        """文脈による重要度スコア"""
        score = 0.0

        # 文の位置による重み付け
        words_in_text = text.split()
        if word in words_in_text:
            position = words_in_text.index(word)
            total_words = len(words_in_text)
            if total_words > 0:
                # 文の前半ほど重要
                position_score = 1.0 - (position / total_words)
                score += position_score * 0.1

        # 出現頻度による重み付け
        word_count = text.count(word)
        if word_count > 1:
            score += min(word_count * 0.05, 0.2)

        # 長さによる重み付け
        if len(word) >= 3:
            score += 0.1

        return min(score, 0.3)

    # MeCab用の既存メソッド（フォールバック用）
    def _calculate_mecab_syntactic_complexity(
        self, words: List[Dict], text: str
    ) -> float:
        """MeCabによる構文複雑さ計算"""
        if not words:
            return 0.0

        length_score = min(len(text) / 15, 1.0)
        pos_diversity = len(set([word["pos"] for word in words])) / len(words)

        return (length_score + pos_diversity) / 2

    def _calculate_mecab_semantic_richness(self, words: List[Dict]) -> float:
        """MeCabによる意味的豊富さ計算"""
        if not words:
            return 0.0

        content_words = len(
            [word for word in words if word["pos"] in ["名詞", "動詞", "形容詞"]]
        )
        return content_words / len(words) if words else 0.0

    def _calculate_mecab_grammatical_correctness(
        self, words: List[Dict], text: str
    ) -> float:
        """MeCabによる文法的正確性計算"""
        if not words:
            return 0.0

        score = 1.0

        particles = len([word for word in words if word["pos"] == "助詞"])
        if particles > 0:
            score += 0.1

        verbs = len([word for word in words if word["pos"] == "動詞"])
        if verbs > 0:
            score += 0.1

        if len(text) >= 3:
            score += 0.1

        return min(score, 1.0)

    def _calculate_sudachi_grammatical_correctness(self, tokens) -> float:
        """SudachiPyによる文法的正確性計算"""
        if not tokens:
            return 0.0

        score = 1.0

        particles = len(
            [token for token in tokens if token.part_of_speech()[0] == "助詞"]
        )
        if particles > 0:
            score += 0.1

        verbs = len([token for token in tokens if token.part_of_speech()[0] == "動詞"])
        if verbs > 0:
            score += 0.1

        return min(score, 1.0)

    def _calculate_janome_grammatical_correctness(self, tokens) -> float:
        """Janomeによる文法的正確性計算"""
        if not tokens:
            return 0.0

        score = 1.0

        particles = len(
            [token for token in tokens if token.part_of_speech.split(",")[0] == "助詞"]
        )
        if particles > 0:
            score += 0.1

        verbs = len(
            [token for token in tokens if token.part_of_speech.split(",")[0] == "動詞"]
        )
        if verbs > 0:
            score += 0.1

        return min(score, 1.0)
