import re
from typing import List, Dict
from collections import defaultdict

class SimpleWordExtractor:
    """シンプルな単語抽出クラス"""
    
    def __init__(self):
        # 基本的な単語パターン
        self.noun_patterns = [
            r'AI|人工知能|機械学習|ディープラーニング|IoT',
            r'スマートフォン|タブレット|コンピュータ|システム|アプリ',
            r'宇宙|火星|月面|衛星|ロケット',
            r'経済|政治|教育|医療|環境|エネルギー',
            r'技術|開発|研究|実験|分析|データ',
            r'企業|会社|組織|政府|自治体'
        ]
        
        self.proper_noun_patterns = [
            r'[A-Z][a-zA-Z]+',  # 英語固有名詞
            r'[ァ-ヴー]{2,}',    # カタカナ語
        ]
    
    def extract_words(self, text: str) -> Dict[str, List[str]]:
        """テキストから単語を抽出"""
        if not text:
            return {"proper_nouns": [], "common_nouns": [], "keywords": []}
        
        result = {
            "proper_nouns": [],
            "common_nouns": [],
            "keywords": []
        }
        
        # カタカナ語・英語（固有名詞として扱う）
        for pattern in self.proper_noun_patterns:
            matches = re.findall(pattern, text)
            result["proper_nouns"].extend(matches)
        
        # 一般名詞
        for pattern in self.noun_patterns:
            matches = re.findall(pattern, text)
            result["common_nouns"].extend(matches)
        
        # キーワード（漢字を含む2文字以上の単語）
        keywords = re.findall(r'[一-龯ぁ-んァ-ヴー]{2,}', text)
        # フィルタリング（助詞・助動詞などを除外）
        filtered_keywords = []
        exclude_patterns = [
            r'^(こと|もの|ため|よう|など|について|により|において|として|という|である|です|ます|した|する|される|れる|られる|せる|させる)$',
            r'^(は|が|を|に|へ|で|と|から|より|まで|の|や|か|も|こそ|さえ|でも|しか|ばかり|だけ|ほど|くらい|など)$'
        ]
        
        for keyword in keywords:
            exclude = False
            for pattern in exclude_patterns:
                if re.match(pattern, keyword):
                    exclude = True
                    break
            if not exclude and len(keyword) >= 2:
                filtered_keywords.append(keyword)
        
        result["keywords"] = filtered_keywords
        
        # 重複除去
        for key in result:
            result[key] = list(set(result[key]))
        
        return result
    
    def get_frequent_words(self, texts: List[str], min_frequency: int = 2) -> Dict[str, int]:
        """頻出単語を取得"""
        word_count = defaultdict(int)
        
        for text in texts:
            extracted = self.extract_words(text)
            for category in extracted:
                for word in extracted[category]:
                    if len(word) >= 2:
                        word_count[word] += 1
        
        frequent_words = {
            word: count for word, count in word_count.items() 
            if count >= min_frequency
        }
        
        return dict(sorted(frequent_words.items(), key=lambda x: x[1], reverse=True))