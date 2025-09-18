import MeCab
import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class NLPProcessor:
    def __init__(self):
        try:
            # MeCabの初期化（chasenフォーマットを使わない）
            dicdir = "/var/lib/mecab/dic/ipadic"
            if os.path.exists(dicdir):
                self.tagger = MeCab.Tagger(f"-d {dicdir}")
            else:
                # フォールバック：デフォルトの辞書を使用
                self.tagger = MeCab.Tagger("")
        except Exception as e:
            logger.warning(f"MeCab初期化エラー: {e}")
            logger.info("MeCabなしで実行します")
            self.tagger = None

    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """テキストからキーワードを抽出"""
        if not self.tagger:
            # MeCabが使用できない場合の簡易的な処理
            return self._simple_keyword_extraction(text, max_keywords)
        
        try:
            # ... existing MeCab processing code ...
            keywords = []
            node = self.tagger.parseToNode(text)
            
            while node:
                if node.feature:
                    features = node.feature.split(',')
                    if len(features) >= 2:
                        pos = features[0]  # 品詞
                        if pos in ['名詞', '動詞', '形容詞']:
                            if len(node.surface) > 1:  # 1文字以上
                                keywords.append(node.surface)
                node = node.next
            
            return list(set(keywords))[:max_keywords]
        except Exception as e:
            logger.error(f"キーワード抽出エラー: {e}")
            return self._simple_keyword_extraction(text, max_keywords)
    
    def _simple_keyword_extraction(self, text: str, max_keywords: int) -> List[str]:
        """MeCabが使用できない場合の簡易的なキーワード抽出"""
        import re
        
        # 簡易的な日本語単語分割
        words = re.findall(r'[ぁ-んァ-ヶ一-龯]+', text)
        # 長さでフィルタリング
        keywords = [word for word in words if len(word) >= 2]
        return list(set(keywords))[:max_keywords]
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """感情分析（簡易版）"""
        # ... existing code ...