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
        text = re.sub(r'[\r\n\t]+', ' ', text)  # 改行・タブを空白に
        text = re.sub(r'\s+', ' ', text)        # 連続空白を単一空白に
        text = re.sub(r'[【】『』「」〔〕［］]', '', text)  # 括弧類削除
        
        # HTMLタグ削除（念のため）
        text = re.sub(r'<[^>]+>', '', text)
        
        # 特殊文字削除
        text = re.sub(r'[©®™]', '', text)
        
        return text.strip()
    
    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """文章を文に分割"""
        if not text:
            return []
        
        # 文末記号で分割
        sentences = re.split(r'[。！？\.\!\?]+', text)
        
        # 短すぎる文や長すぎる文を除外
        valid_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if 10 <= len(sentence) <= 200:  # 適度な長さの文のみ
                valid_sentences.append(sentence)
        
        return valid_sentences
    
    @staticmethod
    def remove_urls_and_mentions(text: str) -> str:
        """URLや@メンションを削除"""
        # URL削除
        text = re.sub(r'https?://[^\s]+', '', text)
        
        # @メンション削除  
        text = re.sub(r'@\w+', '', text)
        
        # ハッシュタグ削除
        text = re.sub(r'#\w+', '', text)
        
        return text.strip()