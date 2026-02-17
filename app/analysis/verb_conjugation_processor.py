# app/analysis/verb_conjugation_processor.py
import MeCab
import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


class VerbConjugationProcessor:
    """動詞の活用形を処理するクラス（第三勢力用）"""

    def __init__(self):
        try:
            self.tagger = MeCab.Tagger("")
            # 初期化テスト
            self.tagger.parse("")
            logger.info("VerbConjugationProcessor initialized successfully")
        except Exception as e:
            logger.error(f"MeCab initialization error: {e}")
            raise RuntimeError(f"Failed to initialize MeCab: {e}")

    def extract_verb_forms(self, text: str) -> List[Dict[str, str]]:
        """テキストから動詞の活用形を抽出"""
        if not text or not isinstance(text, str):
            return []

        try:
            verbs = []
            node = self.tagger.parseToNode(text)

            while node:
                features = node.feature.split(",")
                if len(features) > 0 and features[0] == "動詞":
                    verb_info = {
                        "surface": node.surface,  # 表層形（活用された形）
                        "base_form": features[6]
                        if len(features) > 6
                        else node.surface,  # 基本形
                        "conjugation": features[5]
                        if len(features) > 5
                        else "",  # 活用形
                        "conjugation_type": features[4]
                        if len(features) > 4
                        else "",  # 活用型
                        "pos": features[0],
                        "pos_detail": features[1] if len(features) > 1 else "",
                    }
                    verbs.append(verb_info)
                node = node.next

            logger.info(f"Extracted {len(verbs)} verb forms from text")
            return verbs

        except Exception as e:
            logger.error(f"Error extracting verb forms: {e}")
            return []

    def extract_all_word_forms(self, text: str) -> List[Dict[str, str]]:
        """テキストから品詞付き単語を抽出（動詞は活用形情報付き）"""
        if not text or not isinstance(text, str):
            return []

        try:
            words = []
            node = self.tagger.parseToNode(text)

            # 抽出対象の品詞
            target_pos = ["名詞", "動詞", "形容詞", "形容動詞", "副詞"]

            while node:
                features = node.feature.split(",")
                if len(features) > 0 and features[0] in target_pos:
                    if node.surface.strip():
                        word_info = {
                            "surface": node.surface,
                            "pos": features[0],
                            "pos_detail": features[1] if len(features) > 1 else "",
                            "base_form": features[6]
                            if len(features) > 6
                            else node.surface,
                        }

                        # 動詞の場合は活用形情報も追加
                        if features[0] == "動詞":
                            word_info.update(
                                {
                                    "conjugation": features[5]
                                    if len(features) > 5
                                    else "",
                                    "conjugation_type": features[4]
                                    if len(features) > 4
                                    else "",
                                }
                            )

                        words.append(word_info)
                node = node.next

            # ログ出力を削減（デバッグ時のみ）
            # logger.info(f"Extracted {len(words)} words with forms from text")
            return words

        except Exception as e:
            logger.error(f"Error extracting word forms: {e}")
            return []

    def get_conjugation_patterns(
        self, verbs: List[Dict[str, str]]
    ) -> Dict[str, List[str]]:
        """動詞の活用パターンを分析"""
        patterns = defaultdict(list)

        for verb in verbs:
            base_form = verb["base_form"]
            conjugation = verb["conjugation"]
            conjugation_type = verb["conjugation_type"]

            if base_form and conjugation:
                pattern_key = f"{conjugation_type}_{conjugation}"
                patterns[pattern_key].append(
                    {
                        "base_form": base_form,
                        "surface": verb["surface"],
                        "conjugation": conjugation,
                    }
                )

        return dict(patterns)

    def analyze_verb_usage_in_odai(self, odai_text: str) -> Dict[str, any]:
        """お題での動詞使用パターンを分析"""
        verbs = self.extract_verb_forms(odai_text)

        analysis = {
            "total_verbs": len(verbs),
            "unique_base_forms": len(set(v["base_form"] for v in verbs)),
            "conjugation_types": defaultdict(int),
            "conjugations": defaultdict(int),
            "verb_positions": [],
        }

        for i, verb in enumerate(verbs):
            analysis["conjugation_types"][verb["conjugation_type"]] += 1
            analysis["conjugations"][verb["conjugation"]] += 1
            analysis["verb_positions"].append(
                {
                    "position": i,
                    "base_form": verb["base_form"],
                    "surface": verb["surface"],
                    "conjugation": verb["conjugation"],
                }
            )

        return analysis
