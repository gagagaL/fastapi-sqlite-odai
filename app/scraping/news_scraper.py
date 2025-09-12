import requests
from bs4 import BeautifulSoup
import time
from typing import List, Optional
from dataclasses import dataclass
import re
from urllib.parse import urljoin
import logging

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