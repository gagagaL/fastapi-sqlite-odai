import random
import re
from typing import Dict, List, Tuple, Set
import logging
import os

logger = logging.getLogger(__name__)

class MarkovChainGenerator:
    """マルコフ連鎖を使った文章生成器"""
    
    def __init__(self, order: int = 2):
        """
        初期化
        
        Args:
            order: マルコフ連鎖の階数。何個の単語をまとめて状態とするか
        """
        self.order = order
        self.model = {}
        self.start_states = []
    
    def _create_state(self, words: List[str], i: int) -> Tuple[str, ...]:
        """現在の状態（n個の単語のタプル）を作成"""
        return tuple(words[i:i+self.order])
    
    def train(self, sentences: List[str]):
        """
        文章リストから学習
        
        Args:
            sentences: 学習に使う文章のリスト
        """
        # モデルをリセット
        self.model = {}
        self.start_states = []
        
        for sentence in sentences:
            # 文章を前処理
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 単語に分割
            words = self._tokenize(sentence)
            if len(words) <= self.order:
                continue
                
            # 最初の状態を記録
            first_state = self._create_state(words, 0)
            self.start_states.append(first_state)
            
            # マルコフ連鎖モデルを構築
            for i in range(len(words) - self.order):
                current_state = self._create_state(words, i)
                next_word = words[i + self.order]
                
                if current_state not in self.model:
                    self.model[current_state] = []
                self.model[current_state].append(next_word)
        
        logger.info(f"マルコフモデルを構築: {len(self.model)}状態, {len(self.start_states)}開始状態")
    
    def _tokenize(self, text: str) -> List[str]:
        """テキストを単語に分割"""
        # 簡易的な分割（空白と句読点で分割）
        tokens = re.findall(r'[^、。！？\s]+', text)
        return tokens
    
    def generate(self, max_words: int = 30, seed: str = None) -> str:
        """
        文章を生成
        
        Args:
            max_words: 最大単語数
            seed: 開始単語（指定がなければランダム）
            
        Returns:
            生成された文章
        """
        if not self.model or not self.start_states:
            return "モデルが学習されていません"
        
        # 開始状態を選択
        if seed:
            matching_states = [s for s in self.start_states if seed in s[0]]
            current_state = random.choice(matching_states) if matching_states else random.choice(self.start_states)
        else:
            current_state = random.choice(self.start_states)
        
        # 文章生成
        result = list(current_state)
        
        for _ in range(max_words - self.order):
            if current_state not in self.model:
                break
                
            next_word = random.choice(self.model[current_state])
            result.append(next_word)
            
            # 状態を更新
            current_state = tuple(result[-self.order:])
        
        # 結果を文字列に変換
        return "".join(result)
    
    def train_from_file(self, file_path: str):
        """ファイルから学習"""
        if not os.path.exists(file_path):
            logger.error(f"ファイルが見つかりません: {file_path}")
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 空行を除去
            lines = [line.strip() for line in lines if line.strip()]
            self.train(lines)
            return True
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {e}")
            return False
    
    def generate_variations(self, count: int = 10, max_words: int = 30, seeds: List[str] = None) -> List[str]:
        """複数のバリエーションを生成"""
        results = []
        used_results = set()  # 重複チェック用
        
        for _ in range(count * 2):  # 重複を考慮して多めに生成
            if seeds and len(seeds) > 0:
                seed = random.choice(seeds)
            else:
                seed = None
                
            text = self.generate(max_words, seed)
            
            # 重複チェック
            if text not in used_results and len(results) < count:
                results.append(text)
                used_results.add(text)
                
            if len(results) >= count:
                break
                
        return results