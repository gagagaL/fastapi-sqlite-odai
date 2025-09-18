# app/scraping/advanced_word_extractor.py
import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict, Counter
import unicodedata

class AdvancedWordExtractor:
    """高度な単語抽出エンジン"""
    
    def __init__(self):
        # 固有名詞パターン（拡張版）
        self.proper_noun_patterns = [
            # 会社名
            r'[ァ-ヴー\w]*(?:株式会社|有限会社|合同会社|一般社団法人|一般財団法人)',
            r'(?:株式会社|有限会社|合同会社)[ァ-ヴー\w]*',
            r'[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*(?:\s+(?:Inc|Corp|Ltd|Co|LLC)\.?)?',
            
            # 地名・国名
            r'[ぁ-んァ-ヴー一-龯]{2,}(?:県|府|都|市|区|町|村|島|山|川|湖|海|港|空港)',
            r'(?:北海道|青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|東京|神奈川|新潟|富山|石川|福井|山梨|長野|岐阜|静岡|愛知|三重|滋賀|京都|大阪|兵庫|奈良|和歌山|鳥取|島根|岡山|広島|山口|徳島|香川|愛媛|高知|福岡|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄)',
            
            # 人名（日本語）
            r'[一-龯]{1,3}[ぁ-ん]{1,4}',  # 姓名パターン
            
            # 製品名・ブランド名
            r'iPhone|iPad|Android|Windows|Mac|PlayStation|Nintendo|Tesla|BMW|Mercedes|Toyota',
            r'[A-Z][a-zA-Z]*[0-9]+[a-zA-Z]*',  # 製品番号パターン
            
            # カタカナ語（2文字以上）
            r'[ァ-ヴー]{2,}',
            
            # 英語固有名詞
            r'[A-Z][a-zA-Z]{2,}',
        ]
        
        # 一般名詞パターン（拡張版）
        self.common_noun_patterns = [
            # 技術用語
            r'AI|人工知能|機械学習|ディープラーニング|IoT|DX|デジタル|システム|アプリ(?:ケーション)?|ソフトウェア|ハードウェア|クラウド|データベース|ネットワーク',
            
            # ビジネス用語
            r'企業|会社|組織|事業|プロジェクト|マーケティング|営業|販売|経営|管理|戦略|計画|予算|投資|資金|売上|利益|収益',
            
            # 社会・政治
            r'政府|政治|政策|法律|規制|制度|社会|経済|市場|業界|産業|環境|エネルギー|教育|医療|福祉|インフラ',
            
            # 科学・研究
            r'研究|開発|実験|分析|調査|検証|評価|測定|データ|結果|効果|影響|原因|要因|問題|課題|解決|改善',
            
            # メディア・エンタメ
            r'ニュース|記事|報道|番組|映画|ドラマ|アニメ|ゲーム|音楽|書籍|雑誌|新聞|テレビ|ラジオ|インターネット',
            
            # 金融
            r'銀行|証券|保険|投資|融資|ローン|金利|株式|債券|為替|仮想通貨|ビットコイン|決済|送金',
            
            # 医療・健康
            r'病院|医師|看護師|患者|診療|治療|手術|薬|ワクチン|健康|病気|症状|診断|検査|予防',
            
            # 交通・インフラ
            r'交通|電車|バス|飛行機|自動車|道路|高速道路|空港|駅|港|橋|トンネル|電力|ガス|水道',
        ]
        
        # 除外する単語（助詞、助動詞、よくある語尾など）
        self.exclude_patterns = [
            r'^(?:こと|もの|ため|よう|など|について|により|において|として|という|である|です|ます|した|する|される|れる|られる|せる|させる|できる)$',
            r'^(?:は|が|を|に|へ|で|と|から|より|まで|の|や|か|も|こそ|さえ|でも|しか|ばかり|だけ|ほど|くらい|など|なお|また|さらに|ただし)$',
            r'^(?:今日|明日|昨日|今週|来週|先週|今月|来月|先月|今年|来年|去年|午前|午後|時間|分|秒)$',
            r'^(?:ここ|そこ|あそこ|これ|それ|あれ|この|その|あの|どの|誰|何|いつ|どこ|なぜ|どう)$',
            r'^.{1}$',  # 1文字の単語を除外
            r'^[0-9１２３４５６７８９０]$',  # 1桁の数字を除外（日本語と英語の数字）
        ]
        
        # 重要度の高いキーワードパターン
        self.important_patterns = [
            r'新(?:製品|サービス|技術|システム|機能)',
            r'(?:発表|発売|開始|開発|導入|採用|契約|提携|買収|合併)',
            r'(?:最新|最大|最小|最高|最低|初|世界初|国内初|業界初)',
            r'(?:成長|拡大|増加|減少|向上|改善|悪化|低下)',
        ]
    
    def extract_words(self, text: str) -> Dict[str, List[str]]:
        """テキストから単語を抽出（拡張版）"""
        if not text:
            return {"proper_nouns": [], "common_nouns": [], "keywords": [], "important_terms": []}
        
        # テキストの正規化
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[【】『』「」〔〕［］()（）]', '', text)
        
        result = {
            "proper_nouns": [],
            "common_nouns": [],
            "keywords": [],
            "important_terms": []
        }
        
        # 固有名詞抽出
        for pattern in self.proper_noun_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            result["proper_nouns"].extend(matches)
        
        # 一般名詞抽出
        for pattern in self.common_noun_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            result["common_nouns"].extend(matches)
        
        # 重要語句抽出
        for pattern in self.important_patterns:
            matches = re.findall(pattern, text)
            result["important_terms"].extend(matches)
        
        # キーワード抽出（漢字・ひらがな・カタカナ混合の2文字以上）
        keywords = re.findall(r'[一-龯ぁ-んァ-ヴー]{2,}', text)
        
        # フィルタリング
        filtered_keywords = []
        for keyword in keywords:
            # 除外パターンチェック
            exclude = False
            for pattern in self.exclude_patterns:
                if re.match(pattern, keyword):
                    exclude = True
                    break
            
            if not exclude and len(keyword) >= 2:
                filtered_keywords.append(keyword)
        
        result["keywords"] = filtered_keywords
        
        # 重複除去とクリーニング
        for key in result:
            cleaned = []
            for word in result[key]:
                word = word.strip()
                if word and len(word) >= 2:
                    cleaned.append(word)
            result[key] = list(set(cleaned))
        
        return result
    
    def extract_with_context(self, text: str) -> List[Dict]:
        """文脈付きで単語を抽出"""
        sentences = re.split(r'[。！？\.\!\?]+', text)
        word_contexts = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
                
            extracted = self.extract_words(sentence)
            
            for category, words in extracted.items():
                for word in words:
                    word_contexts.append({
                        "word": word,
                        "category": category,
                        "context": sentence[:100] + "..." if len(sentence) > 100 else sentence,
                        "full_sentence": sentence
                    })
        
        return word_contexts
    
    def get_word_importance_score(self, word: str, text: str) -> float:
        """単語の重要度スコアを計算"""
        score = 0.0
        
        # 出現回数
        frequency = text.count(word)
        score += min(frequency * 0.1, 1.0)
        
        # 文字数（適度な長さが重要）
        if 3 <= len(word) <= 8:
            score += 0.3
        elif 2 <= len(word) <= 10:
            score += 0.1
        
        # カタカナ語（固有名詞の可能性）
        if re.match(r'^[ァ-ヴー]+$', word):
            score += 0.2
        
        # 漢字を含む（専門用語の可能性）
        if re.search(r'[一-龯]', word):
            score += 0.2
        
        # 重要語句パターンマッチ
        for pattern in self.important_patterns:
            if re.search(pattern, word):
                score += 0.5
                break
        
        return min(score, 1.0)
    
    def get_frequent_words_with_scores(self, texts: List[str], min_frequency: int = 2) -> List[Dict]:
        """頻出単語をスコア付きで取得"""
        word_count = defaultdict(int)
        word_contexts = defaultdict(list)
        
        for text in texts:
            extracted = self.extract_words(text)
            for category, words in extracted.items():
                for word in words:
                    if len(word) >= 2:
                        word_count[word] += 1
                        word_contexts[word].append({
                            "category": category,
                            "text": text[:200] + "..." if len(text) > 200 else text
                        })
        
        # 頻度でフィルタリング & スコア計算
        result = []
        for word, frequency in word_count.items():
            if frequency >= min_frequency:
                # 代表的なテキストから重要度スコア計算
                sample_text = word_contexts[word][0]["text"]
                importance = self.get_word_importance_score(word, sample_text)
                
                result.append({
                    "word": word,
                    "frequency": frequency,
                    "importance_score": importance,
                    "category": word_contexts[word][0]["category"],
                    "contexts": word_contexts[word]
                })
        
        # 重要度スコア順でソート
        result.sort(key=lambda x: (x["importance_score"], x["frequency"]), reverse=True)
        return result