import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urljoin
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.database import Base  # 追加
from app.models.news_article import NewsArticle
from app.models.extracted_word import ExtractedWord
from app.database.crud import ExtractedWordCRUD, NewsArticleCRUD
from app.scraping.word_extractor import MeCabWordExtractor
import logging
import ssl
import aiohttp
import re   # 追加
import time # 追加
import MeCab

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapedArticle:
    """スクレイピングした記事データ"""
    title: str
    content: str
    url: str
    source: str

class YahooNewsScraper:
    """Yahoo!ニューススクレイパー"""
    
    def __init__(self):
        self.source_name = "Yahoo!ニュース"
        self.base_url = "https://news.yahoo.co.jp"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        """Yahoo!ニュースの記事リンクを取得"""
        try:
            response = self.session.get(f"{self.base_url}/topics")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # 記事リンクを抽出
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/articles/' in href:
                    full_url = urljoin(self.base_url, href)
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= max_links:
                            break
            
            return links
            
        except Exception as e:
            logger.error(f"Yahoo!ニュース記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        """Yahoo!ニュース記事をスクレイピング"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得
            title_elem = soup.find('h1')
            if not title_elem:
                title_elem = soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            # 本文取得（複数のセレクタを試行）
            content_selectors = [
                '.articleMain',
                '.hbody', 
                '[data-cl-params*="body"]',
                'div[class*="article"]',
                'div[class*="body"]',
                '.sc-cmTdod'
            ]
            
            content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(strip=True)
                    break
            
            if not content:
                # フォールバック: p タグから抽出
                paragraphs = soup.find_all('p')
                content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            # コンテンツの品質チェック
            if len(content) < 100:
                logger.warning(f"コンテンツが短すぎます: {url}")
                return None
            
            # 不要な文字列を除去
            content = re.sub(r'(Yahoo!ニュース|詳細を見る|続きを読む)', '', content)
            
            return ScrapedArticle(
                title=title,
                content=content,
                url=url,
                source=self.source_name
            )
            
        except Exception as e:
            logger.error(f"記事スクレイピングエラー: {url} - {e}")
            return None
    
    def scrape_articles(self, max_articles: int = 5) -> List[ScrapedArticle]:
        """複数記事をスクレイピング"""
        articles = []
        links = self.get_article_links(max_articles * 2)
        
        if not links:
            logger.warning("記事リンクが取得できませんでした。サンプルデータを使用します。")
            # サンプル記事を返す
            return self._get_sample_articles(max_articles)
        
        for i, link in enumerate(links[:max_articles]):
            try:
                logger.info(f"記事取得中 ({i+1}/{max_articles}): {link}")
                article = self.scrape_article(link)
                if article:
                    articles.append(article)
                time.sleep(1)  # 負荷軽減
            except Exception as e:
                logger.warning(f"記事取得失敗: {link} - {e}")
                continue
        
        # 取得できなかった場合はサンプルデータで補完
        if not articles:
            articles = self._get_sample_articles(max_articles)
        
        logger.info(f"{len(articles)}件の記事を取得完了")
        return articles
    
    def _get_sample_articles(self, count: int) -> List[ScrapedArticle]:
        """サンプル記事データ（スクレイピング失敗時のフォールバック）"""
        sample_articles = [
            ScrapedArticle(
                title="AI技術の最新動向について専門家が解説",
                content="人工知能技術の発達により、様々な業界で革新的な変化が起こっています。特に機械学習やディープラーニングの分野では、画像認識や自然言語処理の精度が大幅に向上しており、実用的なアプリケーションが次々と登場しています。専門家によると、今後5年間でAI技術はさらに進歩し、私たちの日常生活により深く浸透していくと予想されています。",
                url="https://example.com/ai-news-sample-1",
                source=self.source_name
            ),
            ScrapedArticle(
                title="宇宙開発の新時代：民間企業の挑戦",
                content="宇宙開発分野において民間企業の存在感が増しています。ロケット技術の発達により、衛星打ち上げコストが大幅に削減され、宇宙ビジネスの可能性が広がっています。火星探査や月面基地建設など、かつては夢物語だった計画が現実味を帯びてきており、宇宙産業の市場規模は今後10年間で大幅な成長が見込まれています。",
                url="https://example.com/space-news-sample-1",
                source=self.source_name
            ),
            ScrapedArticle(
                title="スマートシティ実現に向けた取り組みが加速",
                content="IoT技術やビッグデータ解析を活用したスマートシティの実現に向けた取り組みが世界各地で加速しています。交通渋滞の解消、エネルギー効率の向上、公共サービスの最適化など、様々な分野での改善が期待されています。日本でも複数の都市でスマートシティプロジェクトが進行中で、2030年頃には本格的な運用が始まる予定です。",
                url="https://example.com/smart-city-sample-1",
                source=self.source_name
            )
        ]
        
        return sample_articles[:count]

class NHKNewsScraper:
    """NHKニューススクレイパー（簡易版）"""
    
    def __init__(self):
        self.source_name = "NHK"
        self.base_url = "https://www3.nhk.or.jp"
    
    def scrape_articles(self, max_articles: int = 5) -> List[ScrapedArticle]:
        """NHKニュース記事をスクレイピング（サンプル実装）"""
        sample_articles = [
            ScrapedArticle(
                title="経済政策の新たな方向性について議論",
                content="政府は今年度の経済政策について新たな方針を検討しています。デジタル化の推進や環境技術への投資を重点的に行い、持続可能な経済成長を目指す方針です。有識者会議では、国際競争力の強化と雇用創出の両立が重要な課題として挙げられており、具体的な施策の検討が進められています。",
                url="https://example.com/nhk-economy-1",
                source=self.source_name
            ),
            ScrapedArticle(
                title="教育現場でのデジタル活用が進展",
                content="全国の学校でICT教育の導入が進んでいます。タブレット端末を活用した授業や、オンライン学習プラットフォームの利用により、個々の生徒に合わせた学習が可能になっています。文部科学省は、デジタル技術を活用した教育の効果を検証し、より効果的な学習環境の整備を目指しています。",
                url="https://example.com/nhk-education-1",
                source=self.source_name
            )
        ]
        
        return sample_articles[:max_articles]

def extract_important_words(text: str) -> List[str]:
    """テキストから重要な名詞を抽出"""
    try:
        # MeCabを安全な方法で初期化（chasenフォーマットを使わない）
        tagger = MeCab.Tagger('')
        nodes = tagger.parseToNode(text)
        
        words = []
        while nodes:
            if nodes.feature and nodes.feature.split(",")[0] == "名詞":
                if len(nodes.surface) > 1:  # 1文字以上の単語のみ
                    words.append(nodes.surface)
            nodes = nodes.next
        return words
    except Exception as e:
        logger.error(f"MeCab単語抽出エラー: {e}")
        # MeCabが使用できない場合の簡易的な処理
        return _simple_word_extraction(text)

def _simple_word_extraction(text: str) -> List[str]:
    """MeCabが使用できない場合の簡易的な単語抽出"""
    import re
    # 簡易的な日本語単語分割
    words = re.findall(r'[ぁ-んァ-ヶ一-龯]+', text)
    # 長さでフィルタリング
    return [word for word in words if len(word) >= 2]

async def save_article_with_words(db: Session, article: NewsArticle) -> bool:
    """記事と抽出単語を保存"""
    try:
        # 記事の重複チェック
        existing = db.query(NewsArticle).filter(
            NewsArticle.url == article.url
        ).first()
        
        if existing:
            logger.info(f"重複記事をスキップ: {article.title[:30]}...")
            return False
            
        # 記事を保存
        db.add(article)
        db.flush()  # IDを生成するためにflush
        
        # 重要な単語を抽出して保存
        words = extract_important_words(article.content)
        for word in words:
            word_entry = ExtractedWord(
                word=word,
                source_article_id=article.id,
                word_type="noun",
                frequency=1
            )
            db.add(word_entry)
        
        db.commit()
        logger.info(f"記事と{len(words)}個の単語を保存: {article.title[:30]}...")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"記事保存エラー: {e}")
        return False

# collect_all_news関数内で使用
async def collect_all_news(articles_per_site: int = 2, db: Session = None) -> Dict:
    """全サイトからニュース記事を収集"""
    from .multi_site_scraper import EnhancedMultiSiteScraper
    
    results = {
        'collected': 0,
        'saved': 0,
        'sources': {},
        'articles': []
    }
    
    # 全サイトのスクレイパーを使用
    scraper = EnhancedMultiSiteScraper()
    all_articles = scraper.scrape_all_sites(articles_per_site)
    
    for article_data in all_articles:
        results['collected'] += 1
        
        if db:
            # 記事の重複チェックと保存
            article_data_dict = {
                'title': article_data.title,
                'content': article_data.content,
                'url': article_data.url,
                'source': article_data.source
            }
            
            saved_article = NewsArticleCRUD.create_if_not_exists(db, article_data_dict)
            if saved_article:
                results['saved'] += 1
                # 単語抽出
                extractor = MeCabWordExtractor()
                nouns = extractor.extract_nouns(saved_article.content)
                for noun in nouns:
                    ExtractedWordCRUD.create_or_update_global(db, {
                        'word': noun['word'],
                        'category': noun['category'],
                        'context': noun['context']
                    }, saved_article.id)
        
        results['articles'].append({
            'title': article_data.title,
            'content': article_data.content[:200] + '...',
            'url': article_data.url,
            'source': article_data.source
        })
        
        # ソース別の集計
        source = article_data.source
        results['sources'][source] = results['sources'].get(source, 0) + 1
    
    return results

async def scrape_article(url: str, source: str) -> Optional[NewsArticle]:
    """個別記事のスクレイピング"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=ssl_context) as response:
                if response.status == 200:
                    # エンコーディングを自動検出
                    content_type = response.headers.get('Content-Type', '')
                    if 'charset=' in content_type:
                        charset = content_type.split('charset=')[-1].lower()
                    else:
                        # IT Mediaは通常Shift-JISを使用
                        charset = 'shift-jis' if 'itmedia.co.jp' in url else 'utf-8'
                    
                    try:
                        html = await response.text(encoding=charset, errors='ignore')
                        soup = BeautifulSoup(html, 'lxml')
                        
                        # サイトごとの記事コンテンツ取得ロジック
                        title = soup.title.text.strip() if soup.title else ""
                        content = ""
                        
                        if "itmedia.co.jp" in url:
                            # IT Media用のセレクタを追加
                            content_selectors = [
                                '.inner',
                                '#article-body',
                                '.article-body',
                                '.body'
                            ]
                            for selector in content_selectors:
                                elements = soup.select(selector)
                                if elements:
                                    content = " ".join([p.text.strip() for p in elements])
                                    break
                                    
                        elif "japan.cnet.com" in url:
                            content = " ".join([p.text.strip() for p in soup.select('.article_body p')])
                        elif "jp.techcrunch.com" in url:
                            content = " ".join([p.text.strip() for p in soup.select('.article-content p')])
                        
                        # コンテンツの品質チェック
                        if not content or len(content) < 50:
                            logger.warning(f"Invalid content length for {url}")
                            return None
                        
                        return NewsArticle(
                            title=title,
                            content=content,
                            url=url,
                            source=source
                        )
                    except Exception as e:
                        logger.error(f"Error parsing content from {url}: {str(e)}")
                        return None
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None
    except Exception as e:
        logger.error(f"Error scraping article {url}: {str(e)}")
        return None