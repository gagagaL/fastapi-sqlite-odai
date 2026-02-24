# app/analysis/pattern_based_generator.py
"""
パターン学習型ローカル生成

Gemini等で生成された高品質なお題から構造パターンを抽出・学習し、
新しい単語でローカル生成を行う。
"""

import json
import random
import re
import os
import MeCab
from typing import List, Dict, Optional
from collections import defaultdict


PATTERN_DB_PATH = "app/data/learned_patterns.json"


class PatternBasedGenerator:
    def __init__(self):
        self.tagger = MeCab.Tagger("")
        self.patterns: List[Dict] = []
        self.load_patterns()

    def load_patterns(self):
        """パターンDBを読み込み"""
        if os.path.exists(PATTERN_DB_PATH):
            try:
                with open(PATTERN_DB_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.patterns = data.get("patterns", [])
            except Exception:
                self.patterns = []

    def save_patterns(self):
        """パターンDBを保存"""
        os.makedirs(os.path.dirname(PATTERN_DB_PATH), exist_ok=True)
        with open(PATTERN_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({"patterns": self.patterns}, f, ensure_ascii=False, indent=2)

    def learn_from_odai(self, odai_text: str, source: str = "ai") -> bool:
        """お題から構造パターンを学習"""
        if not odai_text or len(odai_text) < 5:
            return False

        pattern = self._extract_pattern(odai_text)
        if not pattern:
            return False

        if not self._is_duplicate_pattern(pattern):
            self.patterns.append({
                "template": pattern["template"],
                "structure": pattern["structure"],
                "original": odai_text,
                "source": source,
                "noun_count": pattern["noun_count"],
            })
            if len(self.patterns) > 500:
                self.patterns = self.patterns[-500:]
            self.save_patterns()
            return True
        return False

    def _extract_pattern(self, text: str) -> Optional[Dict]:
        """お題から構造パターンを抽出"""
        result = self.tagger.parse(text)
        if not result:
            return None

        nouns = []
        noun_positions = []

        for line in result.strip().split("\n"):
            if line == "EOS" or not line:
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue

            surface = parts[0]
            pos_full = parts[4] if len(parts) > 4 else ""
            pos = pos_full.split("-")[0] if pos_full else ""

            if pos == "名詞" and len(surface) >= 2:
                nouns.append(surface)
                noun_positions.append((surface, text.find(surface)))

        if len(nouns) < 1:
            return None

        template = text
        structure = []

        sorted_nouns = sorted(noun_positions, key=lambda x: -x[1])

        for i, (noun, _) in enumerate(sorted_nouns):
            placeholder = f"{{noun{len(sorted_nouns) - i - 1}}}"
            template = template.replace(noun, placeholder, 1)
            structure.insert(0, {"placeholder": f"noun{len(sorted_nouns) - i - 1}", "original": noun})

        if template == text:
            return None

        return {
            "template": template,
            "structure": structure,
            "noun_count": len(nouns),
        }

    def _is_duplicate_pattern(self, new_pattern: Dict) -> bool:
        """重複パターンかチェック"""
        for p in self.patterns:
            if p["template"] == new_pattern["template"]:
                return True
        return False

    def generate(self, words: List[str], count: int = 10) -> List[Dict]:
        """パターンを使ってお題を生成"""
        if not self.patterns:
            return []

        if not words:
            return []

        nouns = self._filter_nouns(words)
        if not nouns:
            nouns = words

        generated = []
        used_templates = set()
        attempts = 0
        max_attempts = count * 10

        while len(generated) < count and attempts < max_attempts:
            attempts += 1

            pattern = random.choice(self.patterns)
            template = pattern["template"]

            if template in used_templates and len(self.patterns) > count:
                continue

            noun_count = pattern["noun_count"]

            if len(nouns) < noun_count:
                selected_nouns = random.choices(nouns, k=noun_count)
            else:
                selected_nouns = random.sample(nouns, noun_count)

            result = template
            for i, noun in enumerate(selected_nouns):
                result = result.replace(f"{{noun{i}}}", noun)

            if "{noun" in result:
                continue

            if result in [g["text"] for g in generated]:
                continue

            if not self._is_natural(result):
                continue

            generated.append({
                "text": result,
                "method": "pattern_based",
                "source": "local_pattern",
                "quality_score": 0.7 + random.random() * 0.2,
                "used_words": selected_nouns,
            })
            used_templates.add(template)

        return generated

    def _filter_nouns(self, words: List[str]) -> List[str]:
        """名詞のみをフィルタリング"""
        nouns = []
        for word in words:
            if len(word) < 2:
                continue
            result = self.tagger.parse(word)
            if not result:
                continue
            for line in result.strip().split("\n"):
                if line == "EOS" or not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 5:
                    pos = parts[4].split("-")[0] if parts[4] else ""
                    if pos == "名詞":
                        nouns.append(word)
                        break
        return nouns if nouns else words

    def _is_natural(self, text: str) -> bool:
        """生成結果が自然かチェック"""
        if len(text) < 5 or len(text) > 50:
            return False
        if text.count("{") > 0 or text.count("}") > 0:
            return False
        if "　" in text:
            return False
        return True

    def get_stats(self) -> Dict:
        """統計情報を取得"""
        return {
            "pattern_count": len(self.patterns),
            "sources": self._count_sources(),
        }

    def _count_sources(self) -> Dict[str, int]:
        """ソース別のパターン数をカウント"""
        counts = defaultdict(int)
        for p in self.patterns:
            counts[p.get("source", "unknown")] += 1
        return dict(counts)

    def reset(self):
        """パターンDBをリセット"""
        self.patterns = []
        self.save_patterns()


pattern_generator = PatternBasedGenerator()
