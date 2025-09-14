import re
import MeCab
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class MeCabWordExtractor:
    """MeCabを使用して文章から単語を抽出するクラス"""
    
    def __init__(self):
        """MeCab初期化"""
        try:
            # Note: Don't use -Ochasen format
            self.tagger = MeCab.Tagger('')
            # Initialize with empty string
            self.tagger.parse('')
            logger.info("MeCab initialized successfully")
        except Exception as e:
            logger.error(f"MeCab initialization error: {e}")
            raise RuntimeError(f"Failed to initialize MeCab: {e}")

    def extract_nouns(self, text: str) -> List[Dict[str, str]]:
        """テキストから名詞を抽出"""
        if not text or not isinstance(text, str):
            return []

        try:
            nouns = []
            node = self.tagger.parseToNode(text)
            
            while node:
                features = node.feature.split(',')
                if features[0] == '名詞':
                    noun_info = {
                        'word': node.surface,
                        'category': features[1] if len(features) > 1 else '一般',
                        'context': self._get_context(text, node.surface)
                    }
                    nouns.append(noun_info)
                node = node.next

            logger.info(f"Extracted {len(nouns)} nouns from text")
            return nouns

        except Exception as e:
            logger.error(f"Error extracting nouns: {e}")
            return []

    def _get_context(self, text: str, word: str, window: int = 20) -> str:
        """単語の前後の文脈を取得"""
        try:
            word_pos = text.find(word)
            if word_pos == -1:
                return ""
            
            start = max(0, word_pos - window)
            end = min(len(text), word_pos + len(word) + window)
            
            return text[start:end].strip()
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return ""