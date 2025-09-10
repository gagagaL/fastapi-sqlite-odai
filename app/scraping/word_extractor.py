import re
from typing import List, Dict, Tuple
from collections import defaultdict

class SimpleWordExtractor:
    """シンプルな単語抽出（MeCab不要）"""
    
    def __init__(self):
        # よくある固有名詞パターン
        self.proper_noun_patterns = [
            r'[A-Z][a-z]+',  # 英語の固有名詞
            r'[ァ-ヴ]+',      # カタカナ
            r'株式会社\w+',   # 会社名
            r'\w+会社',       # 会社名
            r'\w+大学',       # 大学名
            r'\w+病院',       # 病院名
        ]
        
        # 一般的な名詞パターン
        self.noun_patterns = [
            r'技術|システム|サービス|アプリ|プラン|機能|方法',
            r'問題|課題|解決|改善|対策|方針|政策|計画',
            r'開発|研究|実験|調査|分析|検証|評価',
            r'市場|業界|企業|組織|団体|機関',
            r'データ|情報|ニュース|記事|報告|発表'
        ]
    
    def extract_words(self, text: str) -> Dict[str, List[str]]:
        """テキストから単語を抽出"""
        if not text:
            return {"proper_nouns": [], "common_nouns": [], "keywords": []}
        
        # テキストクリーニング
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        
        result = {
            "proper_nouns": [],
            "common_nouns": [],
            "keywords": []
        }
        
        # 固有名詞抽出
        for pattern in self.proper_noun_patterns:
            matches = re.findall(pattern, text)
            result["proper_nouns"].extend(matches)
        
        # 一般名詞抽出
        for pattern in self.noun_patterns:
            matches = re.findall(pattern, text)
            result["common_nouns"].extend(matches)
        
        # キーワード抽出（長めの単語）
        words = re.findall(r'\w{3,}', clean_text)
        result["keywords"] = [w for w in words if len(w) >= 3]
        
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
                    if len(word) >= 2:  # 2文字以上
                        word_count[word] += 1
        
        # 頻度でフィルタリング
        frequent_words = {
            word: count for word, count in word_count.items() 
            if count >= min_frequency
        }
        
        return dict(sorted(frequent_words.items(), key=lambda x: x[1], reverse=True))