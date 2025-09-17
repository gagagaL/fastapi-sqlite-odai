import MeCab
import re
import unicodedata
from typing import List, Dict, Tuple
from collections import defaultdict, Counter

def init_mecab():
    """MeCabの初期化"""
    try:
        # macOS用のパス
        tagger = MeCab.Tagger('-d /usr/local/lib/mecab/dic/mecab-ipadic-neologd')
    except:
        try:
            # Linux用のパス
            tagger = MeCab.Tagger('-d /usr/lib/x86_64-linux-gnu/mecab/dic/mecab-ipadic-neologd')
        except:
            # フォールバック
            tagger = MeCab.Tagger()
    return tagger

class MeCabWordExtractor:
    """MeCab形態素解析による名詞抽出"""
    
    def __init__(self):
        self.mecab = init_mecab()
        
        # 除外する単語パターン
        self.exclude_patterns = [
            r'^[ぁ-ん]{1,2}$',  # ひらがな1-2文字
            r'^[ァ-ヴ]{1,2}$',  # カタカナ1-2文字
            r'^[a-zA-Z]{1,2}$', # 英字1-2文字
            r'^[0-9]+$',        # 数字のみ
            r'^[０-９]+$',      # 全角数字のみ
        ]
        
        # 除外する名詞（よくある不要語）
        self.exclude_words = {
            'こと', 'もの', 'ため', 'よう', 'ところ', 'とき', 'とこ', 'の', 'ん',
            'それ', 'これ', 'あれ', 'どれ', 'ここ', 'そこ', 'あそこ', 'どこ',
            'すべて', 'みんな', 'だれ', '誰か', '何か', 'なに', '何',
            '時', '時間', '分', '秒', '年', '月', '日', '今日', '明日', '昨日',
            'など', 'なら', 'から', 'まで', 'より', 'ほど', 'くらい',
            'さん', 'ちゃん', 'くん', '様', '氏'
        }
        
        # 重要な名詞カテゴリ（品詞細分類）
        self.important_noun_categories = {
            '名詞,一般': 'general_noun',        # 一般名詞
            '名詞,固有名詞': 'proper_noun',      # 固有名詞
            '名詞,サ変接続': 'suru_noun',        # サ変名詞（動作性名詞）
            '名詞,形容動詞語幹': 'na_adjective',  # 形容動詞語幹
            '名詞,代名詞': 'pronoun',            # 代名詞（除外対象）
            '名詞,数': 'number',                 # 数詞（除外対象）
        }
    
    def is_mecab_available(self) -> bool:
        """MeCabが利用可能かチェック"""
        return self.mecab is not None
    
    def extract_words_mecab(self, text: str) -> Dict[str, List[Dict]]:
        """MeCabを使用して名詞を抽出"""
        if not self.mecab:
            return {"error": "MeCabが利用できません"}
        
        if not text or len(text.strip()) == 0:
            return {"general_nouns": [], "proper_nouns": [], "suru_nouns": []}
        
        # テキストの前処理
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[【】『』「」〔〕［］()（）]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        result = {
            "general_nouns": [],      # 一般名詞
            "proper_nouns": [],       # 固有名詞
            "suru_nouns": [],         # サ変接続名詞
            "compound_nouns": []      # 複合名詞
        }
        
        try:
            # MeCabで形態素解析
            parsed = self.mecab.parse(text)
            lines = parsed.strip().split('\n')
            
            prev_noun = None
            compound_buffer = []
            
            for line in lines:
                if line == 'EOS':
                    # 複合名詞の処理
                    if len(compound_buffer) >= 2:
                        compound = ''.join(compound_buffer)
                        if self._is_valid_word(compound):
                            result["compound_nouns"].append({
                                "word": compound,
                                "components": compound_buffer.copy(),
                                "length": len(compound_buffer)
                            })
                    break
                
                try:
                    surface, features = line.split('\t')
                    features_list = features.split(',')
                    
                    if len(features_list) < 2:
                        compound_buffer = []
                        continue
                    
                    pos = features_list[0]  # 品詞
                    pos_detail = features_list[1]  # 品詞細分類
                    pos_full = f"{pos},{pos_detail}"
                    
                    # 名詞のみを処理
                    if pos == '名詞':
                        # 有効な単語かチェック
                        if self._is_valid_word(surface):
                            word_info = {
                                "word": surface,
                                "pos": pos,
                                "pos_detail": pos_detail,
                                "pos_full": pos_full,
                                "reading": features_list[7] if len(features_list) > 7 else surface,
                                "basic_form": features_list[6] if len(features_list) > 6 else surface
                            }
                            
                            # カテゴリ別に分類
                            if pos_detail == '固有名詞':
                                result["proper_nouns"].append(word_info)
                                compound_buffer.append(surface)
                            elif pos_detail == 'サ変接続':
                                result["suru_nouns"].append(word_info)
                                compound_buffer.append(surface)
                            elif pos_detail == '一般':
                                result["general_nouns"].append(word_info)
                                compound_buffer.append(surface)
                            else:
                                # その他の名詞は一般名詞として扱う
                                if pos_detail not in ['代名詞', '数', '非自立']:
                                    result["general_nouns"].append(word_info)
                                    compound_buffer.append(surface)
                                else:
                                    compound_buffer = []
                        else:
                            compound_buffer = []
                    else:
                        # 最後の複合名詞処理
                        if len(compound_buffer) >= 2:
                            compound = ''.join(compound_buffer)
                            if self._is_valid_word(compound):
                                result["compound_nouns"].append({
                                    "word": compound,
                                    "components": compound_buffer.copy(),
                                    "length": len(compound_buffer)
                                })
                        compound_buffer = []
                        
                except ValueError:
                    continue
                    
        except Exception as e:
            print(f"MeCab解析エラー: {e}")
            return {"error": f"解析エラー: {str(e)}"}
        
        # 重複除去
        for category in result:
            if category != "error":
                seen = set()
                unique_words = []
                for item in result[category]:
                    word = item["word"] if isinstance(item, dict) else item
                    if word not in seen:
                        seen.add(word)
                        unique_words.append(item)
                result[category] = unique_words
        
        return result
    
    def _is_valid_word(self, word: str) -> bool:
        """有効な単語かチェック"""
        if not word or len(word) < 2:
            return False
        
        # 除外単語チェック
        if word in self.exclude_words:
            return False
        
        # パターンチェック
        for pattern in self.exclude_patterns:
            if re.match(pattern, word):
                return False
        
        # 記号・数字のみは除外
        if re.match(r'^[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+$', word):
            return False

        if re.match(r'^[0-9１２３４５６７８９０]$', word):
            return False
        
        return True
    
    def extract_with_context(self, text: str) -> List[Dict]:
        """文脈付きで名詞を抽出"""
        if not self.mecab:
            return []
        
        sentences = re.split(r'[。！？\.\!\?]+', text)
        word_contexts = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue
            
            extracted = self.extract_words_mecab(sentence)
            
            if "error" in extracted:
                continue
            
            for category, words in extracted.items():
                for word_info in words:
                    if isinstance(word_info, dict):
                        word = word_info["word"]
                        pos_detail = word_info.get("pos_detail", category)
                    else:
                        word = word_info
                        pos_detail = category
                    
                    word_contexts.append({
                        "word": word,
                        "category": category,
                        "pos_detail": pos_detail,
                        "context": sentence[:100] + "..." if len(sentence) > 100 else sentence,
                        "full_sentence": sentence
                    })
        
        return word_contexts
    
    def get_word_importance_score(self, word: str, pos_detail: str, text: str) -> float:
        """単語の重要度スコアを計算（MeCab版）"""
        score = 0.0
        
        # 出現回数
        frequency = text.count(word)
        score += min(frequency * 0.15, 1.0)
        
        # 品詞による重み付け
        pos_weights = {
            '固有名詞': 0.8,      # 固有名詞は重要
            'サ変接続': 0.6,      # 動作性名詞も重要
            '一般': 0.4,          # 一般名詞は標準
            'compound_nouns': 0.7  # 複合名詞は重要
        }
        score += pos_weights.get(pos_detail, 0.3)
        
        # 文字数（適度な長さが重要）
        if 3 <= len(word) <= 8:
            score += 0.3
        elif 2 <= len(word) <= 10:
            score += 0.1
        
        # カタカナ語（外来語・技術用語の可能性）
        if re.match(r'^[ァ-ヴー]+$', word):
            score += 0.2
        
        # 漢字を含む（専門用語の可能性）
        if re.search(r'[一-龯]', word):
            score += 0.2
        
        return min(score, 1.0)
    
    def get_frequent_words_with_scores(self, texts: List[str], min_frequency: int = 2) -> List[Dict]:
        """頻出名詞をスコア付きで取得（MeCab版）"""
        if not self.mecab:
            return []
        
        word_count = defaultdict(int)
        word_details = defaultdict(list)
        
        for text in texts:
            extracted = self.extract_words_mecab(text)
            
            if "error" in extracted:
                continue
            
            for category, words in extracted.items():
                for word_info in words:
                    if isinstance(word_info, dict):
                        word = word_info["word"]
                        pos_detail = word_info.get("pos_detail", category)
                    else:
                        word = word_info
                        pos_detail = category
                    
                    if len(word) >= 2:
                        word_count[word] += 1
                        word_details[word].append({
                            "category": category,
                            "pos_detail": pos_detail,
                            "text": text[:200] + "..." if len(text) > 200 else text
                        })
        
        # 頻度でフィルタリング & スコア計算
        result = []
        for word, frequency in word_count.items():
            if frequency >= min_frequency:
                details = word_details[word][0]
                sample_text = details["text"]
                pos_detail = details["pos_detail"]
                
                importance = self.get_word_importance_score(word, pos_detail, sample_text)
                
                result.append({
                    "word": word,
                    "frequency": frequency,
                    "importance_score": importance,
                    "category": details["category"],
                    "pos_detail": pos_detail,
                    "contexts": word_details[word]
                })
        
        # 重要度スコア順でソート
        result.sort(key=lambda x: (x["importance_score"], x["frequency"]), reverse=True)
        return result