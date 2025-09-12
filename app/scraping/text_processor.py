import re
import unicodedata
from typing import List

class TextProcessor:
    """テキスト前処理クラス"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """テキストのクリーニング"""
        if not text:
            return ""
        
        # Unicode正規化
        text = unicodedata.normalize('NFKC', text)
        
        # 不要な文字を削除
        text = re.sub(r'[\r\n\t]+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[【】『』「」〔〕［］]', '', text)
        
        # HTMLタグ削除
        text = re.sub(r'<[^>]+>', '', text)
        
        # 特殊文字削除
        text = re.sub(r'[©®™]', '', text)
        
        return text.strip()
    
    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """文章を文に分割"""
        if not text:
            return []
        
        sentences = re.split(r'[。！？\.\!\?]+', text)
        
        valid_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if 10 <= len(sentence) <= 200:
                valid_sentences.append(sentence)
        
        return valid_sentences