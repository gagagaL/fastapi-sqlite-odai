import requests
from bs4 import BeautifulSoup
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from typing import List, Dict
import aiohttp
import asyncio
import logging
from .multi_site_scraper import BaseScraper, ScrapedArticle

logger = logging.getLogger(__name__)

class NewsPicksScraper(BaseScraper):
    """NewsPicksスクレイパー"""
    
    def __init__(self):
        super().__init__("NewsPicks", "https://newspicks.com")
    
    def get_article_links(self, max_links: int = 10, category: str = None) -> List[str]:
        try:
            # カテゴリに応じたURLを取得
            url = self.get_category_url(category) if category else f"{self.base_url}/news"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # 記事リンクを抽出
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/news/' in href:
                    full_url = urljoin(self.base_url, href)
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= max_links:
                            break
            
            return links
            
        except Exception as e:
            logger.error(f"NewsPicks記事リンク取得エラー: {e}")
            return []
    
    def get_category_url(self, category: str) -> str:
        """NewsPicksのカテゴリ別URLを取得"""
        category_urls = {
            'sports': f"{self.base_url}/news/sports",
            'entertainment': f"{self.base_url}/news/entertainment",
            'politics': f"{self.base_url}/news/politics", 
            'general': f"{self.base_url}/news"
        }
        return category_urls.get(category, f"{self.base_url}/news")
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得
            title_elem = soup.find('h1') or soup.select_one('[class*="title"]')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            # 本文取得
            content_selectors = [
                '[class*="article-body"]',
                '[class*="content"]',
                '.article-text'
            ]
            
            content = ""
            for selector in content_selectors:
                elem = soup.select_one(selector)
                if elem:
                    content = elem.get_text(strip=True)
                    break
            
            if not content:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                logger.warning(f"NewsPicks: コンテンツが短すぎます: {url}")
                return None
            
            return ScrapedArticle(title=title, content=content, url=url, source=self.name)
            
        except Exception as e:
            logger.error(f"NewsPicks記事スクレイピングエラー: {url} - {e}")
            return None

class YonnanaNyuusuScraper(BaseScraper):
    """47NEWS（よんななニュース）スクレイパー"""
    
    def __init__(self):
        super().__init__("47NEWS", "https://www.47news.jp")
    
    def get_article_links(self, max_links: int = 10, category: str = None) -> List[str]:
        try:
            # カテゴリに応じたURLを取得
            url = self.get_category_url(category) if category else f"{self.base_url}/news"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # 記事リンクを抽出
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and ('/news/' in href or href.startswith('/') and len(href) > 10):
                    full_url = urljoin(self.base_url, href)
                    if 'www.47news.jp' in full_url and full_url not in links:
                        links.append(full_url)
                        if len(links) >= max_links:
                            break
            
            return links
            
        except Exception as e:
            logger.error(f"47NEWS記事リンク取得エラー: {e}")
            return []
    
    def get_category_url(self, category: str) -> str:
        """47NEWSのカテゴリ別URLを取得"""
        category_urls = {
            'sports': f"{self.base_url}/sports",
            'entertainment': f"{self.base_url}/entertainment",
            'politics': f"{self.base_url}/politics",
            'general': f"{self.base_url}/news"
        }
        return category_urls.get(category, f"{self.base_url}/news")
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得
            title_elem = soup.find('h1') or soup.select_one('.article-title')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            # 本文取得
            content_selectors = [
                '.article-body',
                '.article-text',
                '[class*="content"]'
            ]
            
            content = ""
            for selector in content_selectors:
                elem = soup.select_one(selector)
                if elem:
                    content = elem.get_text(strip=True)
                    break
            
            if not content:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                return None
            
            return ScrapedArticle(title=title, content=content, url=url, source=self.name)
            
        except Exception as e:
            logger.error(f"47NEWS記事スクレイピングエラー: {url} - {e}")
            return None

class GoogleNewsScraper(BaseScraper):
    """Googleニューススクレイパー（RSSフィード経由）"""
    
    def __init__(self):
        super().__init__("Googleニュース", "https://news.google.com")
        # GoogleニュースはRSSを使用
        self.rss_url = "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja"
    
    def get_article_links(self, max_links: int = 10, category: str = None) -> List[str]:
        try:
            # カテゴリに応じたRSSフィードURLを取得
            rss_url = self.get_category_rss_url(category) if category else self.rss_url
            response = self.session.get(rss_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            links = []
            
            # RSS項目から記事リンクを抽出
            items = soup.find_all('item')
            
            for item in items[:max_links * 2]:  # 余裕を持って取得
                link_elem = item.find('link')
                if link_elem:
                    # GoogleニュースのリダイレクトURLを元URLに変換
                    link = link_elem.get_text()
                    # url=パラメータから実際のURLを抽出
                    if 'url=' in link:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        if 'url' in parsed:
                            actual_url = parsed['url'][0]
                            links.append(actual_url)
                    else:
                        links.append(link)
                    
                    if len(links) >= max_links:
                        break
            
            return links
            
        except Exception as e:
            logger.error(f"Googleニュース記事リンク取得エラー: {e}")
            return []
    
    def get_category_rss_url(self, category: str) -> str:
        """Googleニュースのカテゴリ別RSSフィードURLを取得"""
        category_rss_urls = {
            'sports': "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1ZEdnU0FtVnVHZ0pWVXlnQVAB?hl=ja&gl=JP&ceid=JP:ja",
            'entertainment': "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1ZEdnU0FtVnVHZ0pWVXlnQVAB?hl=ja&gl=JP&ceid=JP:ja",
            'politics': "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?hl=ja&gl=JP&ceid=JP:ja",
            'general': "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja"
        }
        return category_rss_urls.get(category, self.rss_url)
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            # 元のサイトから記事を取得
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得（汎用的なセレクタ）
            title_selectors = ['h1', '[property="og:title"]', 'title']
            title = ""
            for selector in title_selectors:
                elem = soup.select_one(selector)
                if elem:
                    if elem.name == 'meta':
                        title = elem.get('content', '')
                    else:
                        title = elem.get_text(strip=True)
                    if title:
                        break
            
            # 本文取得（汎用的なセレクタ）
            content_selectors = [
                'article',
                '[role="main"]',
                '.article-body',
                '.entry-content',
                '[class*="content"]',
                '[class*="article"]'
            ]
            
            content = ""
            for selector in content_selectors:
                elem = soup.select_one(selector)
                if elem:
                    content = elem.get_text(strip=True)
                    if len(content) > 100:  # 十分な長さがあれば採用
                        break
            
            if not content or len(content) < 100:
                # フォールバック: p タグから抽出
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                return None
            
            # ソースサイト名を取得
            source_domain = urlparse(url).netloc
            source_name = f"Googleニュース ({source_domain})"
            
            return ScrapedArticle(title=title, content=content, url=url, source=source_name)
            
        except Exception as e:
            logger.error(f"Googleニュース記事スクレイピングエラー: {url} - {e}")
            return None

class JijiNewsScraper(BaseScraper):
    """時事通信ニューススクレイパー"""
    
    def __init__(self):
        super().__init__("時事通信", "https://www.jiji.com")
    
    def get_article_links(self, max_links: int = 10, category: str = None) -> List[str]:
        try:
            # カテゴリに応じたURLを取得
            url = self.get_category_url(category) if category else f"{self.base_url}/news"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/jc/' in href:  # 時事通信の記事パターン
                    full_url = urljoin(self.base_url, href)
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= max_links:
                            break
            
            return links
            
        except Exception as e:
            logger.error(f"時事通信記事リンク取得エラー: {e}")
            return []
    
    def get_category_url(self, category: str) -> str:
        """時事通信のカテゴリ別URLを取得"""
        category_urls = {
            'sports': f"{self.base_url}/sports",
            'entertainment': f"{self.base_url}/entertainment",
            'politics': f"{self.base_url}/politics",
            'general': f"{self.base_url}/news"
        }
        return category_urls.get(category, f"{self.base_url}/news")
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_elem = soup.find('h1') or soup.select_one('.ArticleTitle')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            content_elem = soup.select_one('.ArticleBody') or soup.select_one('[class*="article"]')
            if content_elem:
                content = content_elem.get_text(strip=True)
            else:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                return None
            
            return ScrapedArticle(title=title, content=content, url=url, source=self.name)
            
        except Exception as e:
            logger.error(f"時事通信記事スクレイピングエラー: {url} - {e}")
            return None

class AdditionalNewsScraper:
    """拡張版ニュースサイトスクレイパー"""
    
    def __init__(self):
        self.sources = {
            'reuters': 'https://jp.reuters.com/news/technology',
            'nikkei': 'https://www.nikkei.com/technology/',
            'zdnet': 'https://japan.zdnet.com/',
            # 他のニュースソースを追加
        }
    
    async def collect_news(self, articles_per_site: int = 2) -> Dict:
        results = {
            'collected': 0,
            'saved': 0,
            'sources': {}
        }
        # スクレイピング実装
        return results

class EnhancedMultiSiteScraper:
    """拡張版マルチサイトスクレイパー"""
    
    def __init__(self):
        self.scrapers = [
            NewsPicksScraper(),
            YonnanaNyuusuScraper(),
            GoogleNewsScraper(),
            JijiNewsScraper()
        ]
    
    async def collect_all_news(self, articles_per_site: int = 2) -> Dict:
        total_results = {
            'collected': 0,
            'saved': 0,
            'sources': {}
        }
        
        for scraper in self.scrapers:
            try:
                links = scraper.get_article_links(articles_per_site)
                
                for link in links:
                    article = scraper.scrape_article(link)
                    if article:
                        total_results['collected'] += 1
                        source = article.source
                        total_results['sources'][source] = total_results['sources'].get(source, 0) + 1
                
            except Exception as e:
                logger.error(f"スクレイパーエラー {scraper.name}: {e}")
                continue
        
        return total_results