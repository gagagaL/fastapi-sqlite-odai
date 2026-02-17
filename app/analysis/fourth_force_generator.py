# app/analysis/fourth_force_generator.py
import random
import logging
import re
from typing import List, Dict, Optional
from .fourth_force_context_learner import FourthForceContextLearner

logger = logging.getLogger(__name__)


class FourthForceGenerator:
    """第四勢力用のお題生成器（文脈N-gram学習型）"""

    def __init__(self, context_learner: FourthForceContextLearner):
        self.context_learner = context_learner

    def generate_from_words(
        self, words: List[str], count: int = 10
    ) -> List[Dict[str, any]]:
        """与えられた単語からお題を生成"""
        generated_odais = []
        used_texts = set()
        used_words = set()  # 使用済み単語を追跡

        logger.info(
            f"Fourth Force: Starting generation with words={words}, count={count}"
        )

        if not words:
            logger.info("Fourth Force: No words provided")
            return []

        # 生成ループ
        attempts = 0
        max_attempts = count * 20

        while len(generated_odais) < count and attempts < max_attempts:
            attempts += 1

            # まだ使っていない単語を優先的に選択
            unused_words = [w for w in words if w not in used_words]
            if unused_words:
                word = random.choice(unused_words)
            else:
                # 全て使用済みの場合はランダムに選択（再利用）
                word = random.choice(words)

            # 複数の生成方法を試す（必須パターンを優先的に使用）
            # 使用済み単語リストを渡すため、クロージャでキャプチャ
            generation_methods = [
                (
                    lambda w, used=used_words: self._generate_creative_pattern(
                        w, words, used
                    ),
                    0.9,
                ),  # 90% - 必須パターン優先
                (
                    lambda w, used=used_words: self._generate_from_template(
                        w, words, used
                    ),
                    0.05,
                ),  # 5% - テンプレート
                (
                    lambda w, used=used_words: self._generate_from_similar_context(
                        w, words, used
                    ),
                    0.05,
                ),  # 5% - 類似文脈
            ]

            # 重み付きランダム選択
            random_value = random.random()
            cumulative = 0
            generation_method = None
            for method, weight in generation_methods:
                cumulative += weight
                if random_value <= cumulative:
                    generation_method = method
                    break

            odai = generation_method(word) if generation_method else None

            if not odai:
                # それでも生成できない場合はスキップ
                continue

            # 生成されたお題が確実にその単語を含むかチェック
            if word not in odai:
                # 単語が含まれていない場合はスキップ
                continue

            # 重複チェック
            if odai in used_texts:
                continue

            # 品質チェック
            if not self._is_quality_odai(odai):
                continue

            # お題を追加
            quality_score = self._calculate_quality_score(odai)

            generated_odais.append(
                {
                    "text": odai,
                    "method": "fourth_force_context",
                    "selected_word": word,
                    "quality_score": quality_score,
                }
            )
            used_texts.add(odai)
            used_words.add(word)  # 使用済み単語に追加

            logger.info(
                f"Fourth Force: Generated: {odai} (word: {word}, score: {quality_score:.3f})"
            )

        logger.info(
            f"Fourth Force: Final result: {len(generated_odais)} odais generated"
        )
        return generated_odais[:count]

    def _generate_from_template(
        self, word: str, available_words: List[str], used_words: set = None
    ) -> Optional[str]:
        """テンプレートから生成（必ず指定された単語を使用）"""
        templates = self.context_learner.templates

        if not templates:
            return None

        # その単語が学習されているテンプレートを優先
        word_templates = []
        for template in templates:
            # テンプレートに {word} が含まれているか確認
            if "{word}" in template:
                word_templates.append(template)

        # 学習されているテンプレートがある場合はそれを優先、なければ全てから選択
        if word_templates:
            selected_template = random.choice(word_templates)
        else:
            selected_template = random.choice(templates)

        # テンプレートに単語を埋め込む
        try:
            result = selected_template.replace("{word}", word, 1)

            # 絶対に原型を残さないため、複数回の変換を確実に適用
            # 1. テンプレート内の他の名詞を具体的な単語に置き換える（必ず実行）
            result = self._replace_other_nouns(
                result, word, available_words, used_words
            )

            # 2. 他の名詞のさらに別の名詞を置き換える（2回目の変換）
            if random.random() < 0.8:
                result = self._replace_other_nouns(
                    result, word, available_words, used_words
                )

            # 3. 必ず創造性を追加：テンプレートの構造を部分的に変更
            result = self._add_creativity(result, word)

            # 4. さらに創造性を追加（2回目の変更）
            if random.random() < 0.6:
                result = self._add_creativity(result, word)

            return result if result else None
        except:
            return None

    def _verify_is_noun(self, word: str) -> bool:
        """単語が名詞かどうかを形態素解析で確認"""
        try:
            parsed = self.context_learner._parse_text(word)
            if parsed and len(parsed) > 0:
                pos = parsed[0].get("pos", "")
                # 名詞で始まる品詞のみ（名詞,固有名詞、名詞,一般など全ての名詞を含む）
                return pos.startswith("名詞")
            return False
        except Exception:
            return False

    def _get_verb_rentaikei(self, word: str) -> Optional[str]:
        """動詞を連体形に変換（基本形を取得）"""
        if word in self.context_learner.word_info:
            pos = self.context_learner.word_info[word].get("pos", "")
            if pos.startswith("動詞"):
                # 形態素解析して基本形を取得
                parsed = self.context_learner._parse_text(word)
                if parsed and len(parsed) > 0:
                    base_form = parsed[0].get("base_form", word)
                    return base_form if base_form else word
        return word

    def _get_adjective_rentaikei(self, word: str) -> Optional[str]:
        """形容詞を連体形に変換（基本形を取得）"""
        if word in self.context_learner.word_info:
            pos = self.context_learner.word_info[word].get("pos", "")
            if pos.startswith("形容詞") or pos.startswith("形容動詞"):
                # 形態素解析して基本形を取得
                parsed = self.context_learner._parse_text(word)
                if parsed and len(parsed) > 0:
                    base_form = parsed[0].get("base_form", word)
                    # 形容詞の連体形は基本形そのまま（大きい、美しいなど）
                    # ただし「な」で終わる形容動詞の場合は「な」を追加
                    if pos.startswith("形容動詞"):
                        return base_form
                    else:
                        return base_form if base_form else word
        return word

    def _prioritize_concrete_nouns(self, candidate_words: List[str]) -> List[str]:
        """名詞候補を優先順位付け（固有名詞・具体的な名詞を優先）"""
        abstract_concepts = {
            "もの",
            "こと",
            "人",
            "時",
            "場所",
            "ところ",
            "場合",
            "時点",
            "瞬間",
            "場面",
            "経験",
            "体験",
            "思い出",
            "記憶",
            "愛",
            "時間",
            "自由",
            "平和",
            "幸福",
            "運命",
            "希望",
            "夢",
            "現実",
        }

        # 優先順位で分類
        proper_nouns = []  # 固有名詞（最優先）
        concrete_nouns = []  # 具体的な名詞（優先）
        abstract_nouns = []  # 抽象的な概念（低優先度）

        for word in candidate_words:
            # リアルタイムで形態素解析して名詞かどうか確認
            if not self._verify_is_noun(word):
                continue  # 名詞でない場合は除外

            # 品詞情報を取得（word_infoから、または形態素解析から）
            pos = ""
            if word in self.context_learner.word_info:
                pos = self.context_learner.word_info[word].get("pos", "")
            else:
                # word_infoにない場合は形態素解析から取得
                parsed = self.context_learner._parse_text(word)
                if parsed and len(parsed) > 0:
                    pos = parsed[0].get("pos", "")

            # 固有名詞
            if pos == "名詞,固有名詞" or pos.startswith("名詞,固有名詞"):
                proper_nouns.append(word)
            # 抽象的な概念
            elif word in abstract_concepts or len(word) <= 1:
                abstract_nouns.append(word)
            # それ以外は具体的な名詞として扱う
            else:
                concrete_nouns.append(word)

        # 優先順位順に結合：固有名詞 > 具体的な名詞 > 抽象的な概念
        return proper_nouns + concrete_nouns + abstract_nouns

    def _replace_other_nouns(
        self,
        text: str,
        target_word: str,
        available_words: List[str],
        used_words: set = None,
    ) -> str:
        """テンプレート内の他の名詞も具体的な単語に置き換える（品詞を考慮）"""
        if not available_words or len(available_words) < 2:
            return text

        # 95%の確率で他の名詞も複数回置き換える（ほぼ確実に置き換える）
        if random.random() < 0.95:
            # テキストを形態素解析して、名詞の位置を特定
            parsed_words = self.context_learner._parse_text(text)

            # 名詞のみを抽出（全ての名詞タイプを含む）
            noun_positions = []
            for word_info in parsed_words:
                pos = word_info.get("pos", "")
                # 名詞で始まる品詞のみ（名詞,固有名詞、名詞,一般など全ての名詞を含む）
                if pos.startswith("名詞") and word_info["surface"] != target_word:
                    noun_positions.append(
                        {"word": word_info["surface"], "pos": word_info["pos"]}
                    )

            if not noun_positions:
                return text

            # 学習された名詞のみを候補として使用
            # 利用可能な単語と学習された単語から名詞のみを抽出
            learned_words = list(self.context_learner.word_info.keys())
            all_candidate_words = []

            for word in available_words + learned_words:
                # 重複を避ける
                if word in all_candidate_words:
                    continue
                if word == target_word:
                    continue
                if len(word) < 2:
                    continue

                # 品詞情報を確認（名詞のみを厳密に選ぶ）
                is_noun = False

                if word in self.context_learner.word_info:
                    pos = self.context_learner.word_info[word].get("pos", "")
                    # 名詞で始まる品詞のみ
                    if pos.startswith("名詞"):
                        # 念のため形態素解析でも確認
                        if self._verify_is_noun(word):
                            is_noun = True
                else:
                    # word_infoにない場合は形態素解析で確認
                    if self._verify_is_noun(word):
                        is_noun = True

                if is_noun:
                    all_candidate_words.append(word)

            if not all_candidate_words:
                return text

            # 使用済み単語を除外（可能な限り多様な単語を使用）
            if used_words:
                unused_candidates = [
                    w for w in all_candidate_words if w not in used_words
                ]
                if unused_candidates:
                    # 未使用の単語を優先的に使用
                    preferred_candidates = unused_candidates
                else:
                    # 全て使用済みの場合は全候補を使用
                    preferred_candidates = all_candidate_words
            else:
                preferred_candidates = all_candidate_words

            if not preferred_candidates:
                return text

            # 置き換え対象の名詞を選択
            replacement_count = min(random.randint(2, 5), len(noun_positions))
            selected_nouns = random.sample(noun_positions, replacement_count)

            result = text
            replaced_words = set()

            for noun_info in selected_nouns:
                old_word = noun_info["word"]

                # まだ置き換えていない名詞を置き換える
                if old_word not in replaced_words and old_word in result:
                    # 利用可能な名詞候補から選ぶ（未使用を優先）
                    candidate_words = [
                        w
                        for w in preferred_candidates
                        if w not in replaced_words and len(w) >= 2
                    ]

                    # 未使用候補がない場合は全候補から選択
                    if not candidate_words:
                        candidate_words = [
                            w
                            for w in all_candidate_words
                            if w not in replaced_words and len(w) >= 2
                        ]

                    if candidate_words:
                        # 具体的な名詞（名称）を優先的に選択
                        prioritized_candidates = self._prioritize_concrete_nouns(
                            candidate_words
                        )
                        # 前半から優先的に選ぶ（固有名詞や具体的な名詞を優先）
                        # ただし、完全にランダムにすると意味がないので、70%で優先候補から選ぶ
                        if random.random() < 0.7 and len(prioritized_candidates) > 0:
                            # 前半の70%から選択（具体的な名詞を優先）
                            range_end = max(1, int(len(prioritized_candidates) * 0.7))
                            new_word = random.choice(prioritized_candidates[:range_end])
                        else:
                            new_word = random.choice(prioritized_candidates)
                        result = result.replace(old_word, new_word, 1)
                        replaced_words.add(old_word)
                        replaced_words.add(new_word)

                        # 使用済み単語に追加（次の生成で多様性を保つため）
                        if used_words is not None:
                            used_words.add(new_word)

            if result != text:
                return result

        # さらに、抽象的表現（○○）を具体的な名詞に置き換える
        if random.random() < 0.1:
            if "○○" in text:
                # 名詞候補のみから選ぶ
                noun_candidates = []
                for word in available_words:
                    if word in self.context_learner.word_info:
                        pos = self.context_learner.word_info[word].get("pos", "")
                        if pos == "名詞":
                            noun_candidates.append(word)

                if noun_candidates:
                    concrete = random.choice(noun_candidates)
                    result = text.replace("○○", concrete, 1)
                    return result

        return text

    def _ensure_verb_forms(self, text: str) -> str:
        """動詞を終止形・連体形に統一する"""
        result = text

        # 過去形→連体形への変換（終止形・連体形に統一）
        past_to_masu_form = [
            ("した", "する"),
            ("驚いた", "驚く"),
            ("感動した", "感動する"),
            ("困った", "困る"),
            ("笑った", "笑う"),
            ("泣いた", "泣く"),
            ("嬉しかった", "嬉しい"),
            ("悲しかった", "悲しい"),
            ("驚いた", "驚く"),
            ("感動した", "感動する"),
        ]

        for old, new in past_to_masu_form:
            if old in result:
                # 動詞を終止形に変換
                result = result.replace(old, new, 1)

        return result

    def _add_creativity(self, text: str, target_word: str) -> str:
        """テキストに創造性を加える（必ず何か変更する、かつ複数変更を適用）"""
        # まず動詞を終止形・連体形に統一
        text = self._ensure_verb_forms(text)
        result = text

        # より積極的に構造を変更するパターン（動詞は終止形・連体形のみ）
        ending_variations = [
            (
                "で困ること",
                [
                    "で困る場面",
                    "で困る状況",
                    "で困ること",
                    "で困る経験",
                    "に困ること",
                    "が大変なこと",
                ],
            ),
            ("あるある", ["あるあるね", "あるあるを", "あるあること", "あるある話"]),
            ("な人", ["な人って", "な人とは", "な人の特徴", "な人に多いこと"]),
            ("な物", ["なもの", "なものって", "なモノ", "なものの場合"]),
            (
                "すること",  # 連体形（終止形+こと）
                [
                    "すること",
                    "することでの",
                    "すること場面",
                    "すること場合",
                    "すること経験",
                ],
            ),
            (
                "で驚くこと",  # 終止形
                ["で驚くこと", "でびっくり", "で驚き", "で衝撃を受けること"],
            ),
            (
                "で感動すること",  # 終止形
                [
                    "で感動すること",
                    "で感動する場面",
                    "で感動する瞬間",
                    "で心を打つこと",
                ],
            ),
            ("の秘密", ["のヒミツ", "のウラ", "の謎", "の正体"]),
            (
                "で印象的",
                ["で印象的なこと", "で印象深い", "で心に残る", "で記憶に刻まれる"],
            ),
            ("を世界", ["で世界", "が世界", "の世界", "ら世界"]),
            ("期の", ["の", "における", "が", "で"]),
            ("でこんな", ["でこんな", "がこんな", "にこんな", "のこんな"]),
        ]

        # 複数の変更を同時に適用（原型を残さない）
        applied_changes = 0

        # 1. 語尾を変更（複数箇所を変更）
        for old_ending, new_endings in ending_variations:
            if old_ending in result and applied_changes < 2:  # 最大2箇所まで
                new_ending = random.choice(new_endings)
                result = result.replace(old_ending, new_ending, 1)
                applied_changes += 1

        # 2. 助詞を変更
        particle_variations = [
            ("で", ["に", "が", "へ", "から"]),
            ("に", ["で", "が", "へ", "から"]),
            ("の", ["が", "を", "で", "に"]),
            ("が", ["で", "に", "を", "へ"]),
            ("を", ["で", "に", "が", "へ"]),
        ]

        # 最大2箇所まで助詞を変更
        for old_particle, new_particles in particle_variations:
            if (
                old_particle in result
                and target_word + old_particle not in result
                and applied_changes < 4
            ):
                new_particle = random.choice(new_particles)
                result = result.replace(old_particle, new_particle, 1)
                applied_changes += 1
                if applied_changes >= 4:
                    break

        # 3. それでも変更がない場合は、語尾に追加または前置
        if applied_changes == 0:
            # 50%の確率で語尾追加、50%の確率で語頭追加
            if random.random() < 0.5:
                additions = ["こと", "もの", "人", "瞬間", "場面", "経験", "場合", "時"]
                addition = random.choice(additions)
                result = result + f"な{addition}"
            else:
                prefixes = ["まさに", "確かに", "実は", "よくある", "あるある"]
                prefix = random.choice(prefixes)
                result = f"{prefix}{result}"

        return result

    def _generate_from_similar_context(
        self, word: str, available_words: List[str], used_words: set = None
    ) -> Optional[str]:
        """類似の文脈を使って生成（必ず指定された単語を使用）"""
        # 類似の単語を見つける
        similar_word = self.context_learner.get_similar_context(word, available_words)

        if not similar_word:
            # 類似の単語がない場合は、元の単語の例文を取得してテンプレート化
            if word in self.context_learner.word_info:
                examples = self.context_learner.word_info[word]["examples"]
                if examples:
                    example = random.choice(examples)
                    result = self._create_template_from_example(
                        example, word, available_words, used_words
                    )
                    if result:
                        return result

            # 他の利用可能な単語の例文を参考にするが、必ず元の単語を使う
            examples = []
            for w in available_words:
                if w in self.context_learner.word_info:
                    examples.extend(self.context_learner.word_info[w]["examples"])
                    if len(examples) >= 3:
                        break

            if examples:
                # 例文の構造を真似して生成
                example = random.choice(examples)
                result = self._create_template_from_example(
                    example, word, available_words, used_words
                )
                if result:
                    return result

            return None

        # 類似の単語の例文を取得
        if similar_word in self.context_learner.word_info:
            examples = self.context_learner.word_info[similar_word]["examples"]
            if examples:
                example = random.choice(examples)

                # 品詞が一致する場合のみ置き換え（名詞の位置には名詞のみ）
                similar_pos = self.context_learner.word_info[similar_word].get(
                    "pos", ""
                )
                word_pos = self.context_learner.word_info.get(word, {}).get("pos", "")

                if similar_pos == word_pos and word_pos == "名詞":
                    # 必ず元の単語を置き換え
                    result = example.replace(similar_word, word, 1)

                    # 例文の他の名詞も複数置き換える（高確率）
                    result = self._replace_other_nouns(
                        result, word, available_words, used_words
                    )

                    # 創造性を追加：語尾を変更したり、構造を微調整
                    result = self._add_creativity(result, word)

                    return result if result and word in result else None

        return None

    def _generate_creative_pattern(
        self, word: str, available_words: List[str], used_words: set = None
    ) -> Optional[str]:
        """創造的なパターンを生成（テンプレートを組み合わせたり、新しい構造を作成）"""
        templates = self.context_learner.templates

        # 完全に新しいパターンも生成（85%の確率） - 必須パターンを優先的に使用
        if random.random() < 0.85:
            return self._generate_original_pattern(word, available_words, used_words)

        if not templates or len(templates) < 2:
            return None

        try:
            # 2つのテンプレートを組み合わせる
            template1 = random.choice(templates)
            template2 = random.choice(templates)

            # テンプレートの語尾部分を切り出して組み合わせ
            if "{word}" in template1 and "{word}" in template2:
                # 両方に {word} がある場合、異なる語尾を組み合わせ
                result1 = template1.replace("{word}", word, 1)
                result2 = template2.replace("{word}", word, 1)

                # 30%の確率で語尾を組み合わせ
                if random.random() < 0.3:
                    # より創造的なバリエーション
                    endings = ["こと", "場面", "経験", "瞬間", "人", "物"]
                    random_ending = random.choice(endings)

                    # 基本構造 + ランダム語尾
                    if word + "で困る" in result1 or word + "がある" in result1:
                        return f"{word}で{random_ending}あるある"
                    elif word + "な人" in result1:
                        return f"{word}な{random_ending}"
                    else:
                        return result1
                else:
                    return result1

            # 単純なテンプレートから生成
            selected_template = random.choice(templates)
            result = selected_template.replace("{word}", word, 1)
            result = self._add_creativity(result, word)
            return result

        except:
            return None

    def _generate_original_pattern(
        self, word: str, available_words: List[str], used_words: set = None
    ) -> Optional[str]:
        """完全にオリジナルのパターンを生成（指定パターンを必ず使用）"""
        # 指定された必須パターン（6 + 2 + 5 + 5 + 6 + 3 + 2 + 2 = 31パターン）
        required_patterns = [
            # 名詞の名詞 - 6パターン
            lambda w, w2: f"{w}の{w2}",
            lambda w, w2: f"{w}の{w2}",
            lambda w, w2: f"{w}の{w2}",
            lambda w, w2: f"{w}強化月間",
            lambda w, w2: f"{w}の{w2}",
            lambda w, w2: f"{w}の嘘豆知識",
            lambda w, w2: f"メカ{w2}",
            lambda w, w2: f"かわいそうな{w}という絵本",
            lambda w: f"{w}めいている",
            lambda w: f"なんか怖い{w}",
            lambda w: f"{w}が主役の恋愛ドラマ",
            lambda w: f"{w}がパッケージのお菓子",
            lambda w: f"{w}がモチーフのクソゲー",
            lambda w, w2: f"{w}{w2}事件",
            lambda w: f"{w}連続殺人事件",
            lambda w, w2: f"{w}{w2}問題",
            lambda w: f"最近の{w}ときたら",
            lambda w, w2: f"最近の{w}ときたら{w2}で",
            lambda w: f"{w}のアンチスレ",
            lambda w: f"{w}のお話",
            # 名詞名詞 - 5パターン
            lambda w, w2: f"{w}{w2}",
            lambda w, w2: f"{w}{w2}",
            lambda w, w2: f"この{w}、{w2}だな。なんでそう思った？",
            lambda w, w2: f"この{w}、{w2}だな。なんでそう思った？",
            lambda w, w2: f"{w}が{w2}の世界",
            # 名詞が名詞の世界 - 3パターン
            lambda w,
            w2: f"めちゃくちゃ不機嫌そうな男が電話しながら{w}とメモしていました。どんな内容の電話だったんですか？",
            lambda w, w2: f"{w}が{w2}の世界",
            lambda w, w2: f"{w}人間がブチギレている理由",
            # 形容詞名詞 - 2パターン（形容詞は連体形）
            lambda adj, noun: f"{adj}{noun}",
            lambda adj, noun: f"{adj}{noun}",
            lambda adj, noun: f"{adj}{noun}",
            # 動詞名詞 - 2パターン（動詞は連体形）
            lambda verb, noun: f"{verb}{noun}",
            lambda verb, noun: f"{verb}{noun}",
        ]

        # 利用可能な他の固有名詞を取得（品詞を考慮、固有名詞のみ）
        # リアルタイムで形態素解析して確認
        all_other_nouns = []
        for w in available_words:
            if w == word:
                continue
            # まずword_infoの品詞情報を確認
            if w in self.context_learner.word_info:
                pos = self.context_learner.word_info[w].get("pos", "")
                if pos == "名詞,固有名詞" or pos.startswith("名詞,固有名詞"):
                    # 念のため形態素解析でも確認
                    if self._verify_is_noun(w):
                        all_other_nouns.append(w)
            else:
                # word_infoにない場合は形態素解析で確認
                if self._verify_is_noun(w):
                    parsed = self.context_learner._parse_text(w)
                    if parsed and len(parsed) > 0:
                        pos = parsed[0].get("pos", "")
                        # 固有名詞を優先
                        if pos == "名詞,固有名詞" or pos.startswith("名詞,固有名詞"):
                            all_other_nouns.append(w)
                        # 固有名詞でない場合も名詞なら追加（次のフォールバック処理で使う）
                        elif pos.startswith("名詞"):
                            # ここでは追加しない（次のフォールバック処理で追加される）
                            pass

        # 固有名詞がない場合は通常の名詞を使用（フォールバック、厳密に名詞のみ）
        if not all_other_nouns:
            for w in available_words:
                if w == word:
                    continue
                # word_infoの品詞情報を確認
                if w in self.context_learner.word_info:
                    pos = self.context_learner.word_info[w].get("pos", "")
                    if pos.startswith("名詞"):
                        # 念のため形態素解析でも確認
                        if self._verify_is_noun(w):
                            all_other_nouns.append(w)
                else:
                    # word_infoにない場合は形態素解析で確認
                    if self._verify_is_noun(w):
                        all_other_nouns.append(w)

        # 使用済み単語を除外して、多様な単語を使用
        if used_words and all_other_nouns:
            unused_nouns = [w for w in all_other_nouns if w not in used_words]
            if unused_nouns:
                # 未使用の単語を優先的に使用
                other_nouns = unused_nouns
            else:
                # 全て使用済みの場合は全候補を使用
                other_nouns = all_other_nouns
        else:
            other_nouns = all_other_nouns

        # 形容詞候補を取得（学習データから）
        adjectives = []
        learned_words = list(self.context_learner.word_info.keys())
        for w in available_words + learned_words:
            if w in self.context_learner.word_info:
                pos = self.context_learner.word_info[w].get("pos", "")
                if pos.startswith("形容詞") or pos.startswith("形容動詞"):
                    adjectives.append(w)
                    if len(adjectives) >= 10:  # 最大10個まで
                        break

        # 動詞候補を取得（学習データから）
        verbs = []
        for w in available_words + learned_words:
            if w in self.context_learner.word_info:
                pos = self.context_learner.word_info[w].get("pos", "")
                if pos.startswith("動詞"):
                    verbs.append(w)
                    if len(verbs) >= 10:  # 最大10個まで
                        break

        # パターンに応じて適切な関数を選択
        # 90%の確率で必須パターンを使用（絶対に出力するため）
        random_val = random.random()

        if random_val < 0.70 and len(other_nouns) > 0:
            # 70%の確率で名詞と名詞を組み合わせたパターン
            # 具体的な名詞（名称）を優先的に選択
            prioritized_nouns = self._prioritize_concrete_nouns(other_nouns)
            # 70%で優先候補（固有名詞や具体的な名詞）から選択
            if random.random() < 0.7 and len(prioritized_nouns) > 0:
                range_end = max(1, int(len(prioritized_nouns) * 0.7))
                other_noun = random.choice(prioritized_nouns[:range_end])
            else:
                other_noun = random.choice(prioritized_nouns)

            # 実際のインデックスを確認：
            # 0-5: 名詞の名詞（6個）
            # 6-7: 名詞名詞のその他（2個）
            # 8-12: 名詞あるある（5個、1引数なので含めない）
            # 13-18: 名詞名詞事件など（6個）
            # 19-23: 名詞名詞（5個）
            # 24-26: 名詞が名詞の世界（3個）
            # 27-28: 形容詞名詞（2個）
            # 29-30: 動詞名詞（2個）

            # 名詞の名詞パターン（6パターン、インデックス0-5）
            patterns_with_nouns = required_patterns[0:6]
            # 名詞名詞事件パターン（6パターン、インデックス13-18）
            patterns_with_event = required_patterns[13:19]
            # 名詞名詞パターン（5パターン、インデックス19-23）
            patterns_with_nouns_combo = required_patterns[19:24]
            # 名詞が名詞の世界パターン（3パターン、インデックス24-26）
            patterns_with_world = required_patterns[24:27]
            # 形容詞名詞パターン（2パターン、インデックス27-28）
            patterns_adj_noun = required_patterns[27:29]
            # 動詞名詞パターン（2パターン、インデックス29-30）
            patterns_verb_noun = required_patterns[29:31]

            # すべての組み合わせパターン（24パターン）
            all_patterns = (
                patterns_with_nouns
                + patterns_with_event
                + patterns_with_nouns_combo
                + patterns_with_world
                + patterns_adj_noun
                + patterns_verb_noun
            )
            pattern_func = random.choice(all_patterns)

            # パターンタイプを判定
            index_in_all = all_patterns.index(pattern_func)
            adj_noun_start = (
                len(patterns_with_nouns)
                + len(patterns_with_event)
                + len(patterns_with_nouns_combo)
                + len(patterns_with_world)
            )
            verb_noun_start = adj_noun_start + len(patterns_adj_noun)

            if adj_noun_start <= index_in_all < verb_noun_start:
                # 形容詞名詞パターン
                if len(adjectives) > 0:
                    adj = random.choice(adjectives)
                    adj = self._get_adjective_rentaikei(adj)  # 連体形に変換
                    if used_words is not None:
                        used_words.add(adj)
                    return pattern_func(adj, other_noun)
                else:
                    # 形容詞がない場合は名詞パターンにフォールバック
                    if used_words is not None:
                        used_words.add(other_noun)
                    return pattern_func(word, other_noun)
            elif index_in_all >= verb_noun_start:
                # 動詞名詞パターン
                if len(verbs) > 0:
                    verb = random.choice(verbs)
                    verb = self._get_verb_rentaikei(verb)  # 連体形に変換
                    if used_words is not None:
                        used_words.add(verb)
                    return pattern_func(verb, other_noun)
                else:
                    # 動詞がない場合は名詞パターンにフォールバック
                    if used_words is not None:
                        used_words.add(other_noun)
                    return pattern_func(word, other_noun)

            # その他のパターンは通常通り名詞を使用
            if used_words is not None:
                used_words.add(other_noun)
            return pattern_func(word, other_noun)
        elif random_val < 0.95:
            # 25%の確率で名詞あるあるパターン（5パターン、1引数の関数）
            patterns_aruaru = [
                lambda w: f"{w}あるある",
                lambda w: f"{w}あるある",
                lambda w: f"{w}あるある",
                lambda w: f"{w}あるある",
                lambda w: f"{w}あるある",
            ]
            pattern_func = random.choice(patterns_aruaru)
            return pattern_func(word)
        else:
            # 残りは既存のパターン
            new_patterns = [
                lambda w: f"{w}で印象的なこと",
                lambda w: f"{w}で印象深い瞬間",
                lambda w: f"{w}で記憶に残ること",
                lambda w: f"{w}で印象的な経験",
                lambda w: f"{w}で印象的な場面",
                lambda w: f"{w}で記憶に焼き付くこと",
                lambda w: f"{w}で印象的な光景",
                lambda w: f"{w}で印象的な体験",
                lambda w: f"{w}で印象的な思い出",
                lambda w: f"{w}で印象的なエピソード",
                lambda w: f"{w}で驚いたこと",
                lambda w: f"{w}で感動したこと",
                lambda w: f"{w}で笑ったこと",
                lambda w: f"{w}で泣いたこと",
            ]
            pattern_func = random.choice(new_patterns)
            return pattern_func(word)

    def _create_template_from_example(
        self,
        example: str,
        word: str,
        available_words: List[str],
        used_words: set = None,
    ) -> Optional[str]:
        """例文からテンプレートを作成して単語を埋め込む（他の名詞も置き換える）"""
        try:
            # 例文を解析
            parsed_words = self.context_learner._parse_text(example)
            # 名詞で始まる品詞のみ（名詞,固有名詞、名詞,一般など全ての名詞を含む）
            nouns = [w for w in parsed_words if w.get("pos", "").startswith("名詞")]

            if not nouns:
                return None

            # 最初の名詞を置き換え
            first_noun = nouns[0]["surface"]
            result = example.replace(first_noun, word, 1)

            # 他の名詞も複数置き換える（高確率）
            result = self._replace_other_nouns(
                result, word, available_words, used_words
            )

            # 構造を変更
            result = self._add_creativity(result, word)

            return result if result else None
        except:
            return None

    def _calculate_quality_score(self, text: str) -> float:
        """品質スコアを計算"""
        if not text:
            return 0.0

        score = 0.3  # 基本スコア

        # 長さスコア
        length = len(text)
        if 5 <= length <= 12:
            score += 0.3
        elif 13 <= length <= 20:
            score += 0.2
        else:
            score -= 0.1

        # お題らしさスコア
        odai_indicators = [
            "あるある",
            "で困る",
            "な人",
            "な物",
            "すること",
            "したこと",
            "の秘密",
            "で驚いた",
            "の特徴",
            "の理由",
        ]
        if any(indicator in text for indicator in odai_indicators):
            score += 0.3

        # 多様性スコア（単語の種類）
        words = text.split()
        unique_words = len(set(words))
        if unique_words >= 2:
            score += 0.1

        # ランダム要素
        score += random.random() * 0.1

        return max(0.0, min(1.0, score))

    def _is_quality_odai(self, text: str) -> bool:
        """お題の品質をチェック"""
        if not text:
            return False

        if len(text) < 3 or len(text) > 30:
            return False

        # 重複した単語のチェック
        words = text.split()
        if len(set(words)) < len(words) * 0.5 and len(words) > 3:
            return False

        return True

    def get_generation_stats(self) -> Dict[str, any]:
        """生成統計を取得"""
        return {
            "learning_stats": self.context_learner.get_learning_stats(),
            "generation_settings": {
                "max_length": 30,
                "min_length": 3,
                "use_context_patterns": True,
                "use_templates": True,
                "quality_threshold": 0.3,
            },
            "available_methods": ["context_n_gram", "template"],
        }
