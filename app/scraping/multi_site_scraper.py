# app/scraping/multi_site_scraper.py
import requests
from bs4 import BeautifulSoup
import time
from typing import List, Optional, Dict
from dataclasses import dataclass
import re
from urllib.parse import urljoin, urlparse
import logging
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapedArticle:
    """スクレイピングした記事データ"""
    title: str
    content: str
    url: str
    source: str

class BaseScraper(ABC):
    """スクレイパーの基底クラス"""
    
    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    @abstractmethod
    def get_article_links(self, max_links: int = 10) -> List[str]:
        """記事リンクを取得"""
        pass
    
    @abstractmethod
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        """単一記事をスクレイピング"""
        pass
    
    def scrape_articles(self, max_articles: int = 5) -> List[ScrapedArticle]:
        """複数記事をスクレイピング"""
        articles = []
        try:
            links = self.get_article_links(max_articles * 2)
            
            if not links:
                logger.warning(f"{self.name}: 記事リンクが取得できませんでした")
                return []
            
            for i, link in enumerate(links[:max_articles]):
                try:
                    logger.info(f"{self.name}: 記事取得中 ({i+1}/{max_articles}): {link}")
                    article = self.scrape_article(link)
                    if article:
                        articles.append(article)
                    time.sleep(1)  # レート制限
                except Exception as e:
                    logger.warning(f"{self.name}: 記事取得失敗: {link} - {e}")
                    continue
            
            logger.info(f"{self.name}: {len(articles)}件の記事を取得完了")
            
        except Exception as e:
            logger.error(f"{self.name}: スクレイピングエラー: {e}")
        
        return articles

class YahooNewsScraper(BaseScraper):
    """Yahoo!ニューススクレイパー"""
    
    def __init__(self):
        super().__init__("Yahoo!ニュース", "https://news.yahoo.co.jp")
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        try:
            response = self.session.get(f"{self.base_url}/topics", timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # 複数のセレクタパターンを試行
            selectors = [
                'a[href*="/articles/"]',
                'a[href*="/pickup/"]',
                'a[data-ylk*="article"]'
            ]
            
            for selector in selectors:
                for link in soup.select(selector):
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.base_url, href) if href.startswith('/') else href
                        if full_url not in links and '/articles/' in full_url:
                            links.append(full_url)
                            if len(links) >= max_links:
                                break
                if len(links) >= max_links:
                    break
            
            return links
            
        except Exception as e:
            logger.error(f"Yahoo!ニュース記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得
            title_selectors = ['h1', '[data-testid="headline"]', '.headline', 'title']
            title = ""
            for selector in title_selectors:
                elem = soup.select_one(selector)
                if elem:
                    title = elem.get_text(strip=True)
                    break
            
            # 本文取得
            content_selectors = [
                '.articleMain',
                '.hbody',
                '[data-testid="paragraphs"]',
                '.sc-cmTdod',
                'div[class*="article"]'
            ]
            
            content = ""
            for selector in content_selectors:
                elem = soup.select_one(selector)
                if elem:
                    content = elem.get_text(strip=True)
                    break
            
            if not content:
                # フォールバック
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:  # 閾値を下げる
                logger.warning(f"コンテンツが短すぎます: {url}")
                return None
            
            return ScrapedArticle(title=title, content=content, url=url, source=self.name)
            
        except Exception as e:
            logger.error(f"Yahoo記事スクレイピングエラー: {url} - {e}")
            return None

class NHKNewsScraper(BaseScraper):
    """NHKニューススクレイパー"""
    
    def __init__(self):
        super().__init__("NHK", "https://www3.nhk.or.jp")
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        try:
            response = self.session.get(f"{self.base_url}/news/", timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/news/' in href and href.endswith('.html'):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= max_links:
                            break
            
            return links
            
        except Exception as e:
            logger.error(f"NHKニュース記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            content_selectors = [
                '.module--detail-content',
                '.body-text',
                'section[class*="detail"]'
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
            logger.error(f"NHK記事スクレイピングエラー: {url} - {e}")
            return None

class AsahiNewsScraper(BaseScraper):
    """朝日新聞デジタルスクレイパー"""
    
    def __init__(self):
        super().__init__("朝日新聞", "https://www.asahi.com")
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        try:
            response = self.session.get(f"{self.base_url}/news/", timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
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
            logger.error(f"朝日新聞記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_elem = soup.find('h1') or soup.select_one('.Title')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            content_elem = soup.select_one('.ArticleBody') or soup.select_one('[data-module="ArticleBody"]')
            if content_elem:
                content = content_elem.get_text(strip=True)
            else:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                return None
            
            return ScrapedArticle(title=title, content=content, url=url, source=self.name)
            
        except Exception as e:
            logger.error(f"朝日新聞記事スクレイピングエラー: {url} - {e}")
            return None

class MainichiNewsScraper(BaseScraper):
    """毎日新聞スクレイパー"""
    
    def __init__(self):
        super().__init__("毎日新聞", "https://mainichi.jp")
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        try:
            response = self.session.get(f"{self.base_url}/news/", timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
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
            logger.error(f"毎日新聞記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            content_elem = soup.select_one('.ArticleText') or soup.select_one('[class*="article"]')
            if content_elem:
                content = content_elem.get_text(strip=True)
            else:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                return None
            
            return ScrapedArticle(title=title, content=content, url=url, source=self.name)
            
        except Exception as e:
            logger.error(f"毎日新聞記事スクレイピングエラー: {url} - {e}")
            return None

class ITmediaNewsScraper(BaseScraper):
    """ITmediaニューススクレイパー"""
    
    def __init__(self):
        super().__init__("ITmedia", "https://www.itmedia.co.jp")
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        try:
            response = self.session.get(f"{self.base_url}/news/", timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/news/' in href and href.endswith('.html'):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= max_links:
                            break
            
            return links
            
        except Exception as e:
            logger.error(f"ITmediaニュース記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            content_elem = soup.select_one('.inner') or soup.select_one('[class*="body"]')
            if content_elem:
                content = content_elem.get_text(strip=True)
            else:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                return None
            
            return ScrapedArticle(title=title, content=content, url=url, source=self.name)
            
        except Exception as e:
            logger.error(f"ITmedia記事スクレイピングエラー: {url} - {e}")
            return None

class MultiSiteScraper:
    """複数サイト統合スクレイパー"""
    
    def __init__(self):
        self.scrapers = [
            YahooNewsScraper(),
            NHKNewsScraper(),
            AsahiNewsScraper(),
            MainichiNewsScraper(),
            ITmediaNewsScraper()
        ]
    
    def scrape_all_sites(self, articles_per_site: int = 3) -> List[ScrapedArticle]:
        """全サイトから記事を収集"""
        all_articles = []
        
        for scraper in self.scrapers:
            try:
                logger.info(f"=== {scraper.name} から記事を収集開始 ===")
                articles = scraper.scrape_articles(articles_per_site)
                all_articles.extend(articles)
                
                # サイト間でのレート制限
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"{scraper.name} でエラー: {e}")
                continue
        
        logger.info(f"=== 全サイト収集完了: {len(all_articles)}件 ===")
        return all_articles
    
    def get_available_sources(self) -> List[str]:
        """利用可能なニュースソース一覧を取得"""
        return [scraper.name for scraper in self.scrapers]

class EnhancedMultiSiteScraper:
    """拡張版複数サイト統合スクレイパー"""
    
    def __init__(self):
        # 既存のスクレイパー + 新規追加
        from .multi_site_scraper import YahooNewsScraper, NHKNewsScraper, AsahiNewsScraper, MainichiNewsScraper, ITmediaNewsScraper
        
        self.scrapers = [
            YahooNewsScraper(),
            NHKNewsScraper(),
            AsahiNewsScraper(),
            MainichiNewsScraper(),
            ITmediaNewsScraper(),
            NewsPicksScraper(),          # 新規追加
            YonnanaNyuusuScraper(),      # 新規追加
            GoogleNewsScraper(),         # 新規追加
            JijiNewsScraper(),           # 新規追加
        ]
    
    def scrape_all_sites(self, articles_per_site: int = 2) -> List[ScrapedArticle]:
        """全サイトから記事を収集"""
        all_articles = []
        
        for scraper in self.scrapers:
            try:
                logger.info(f"=== {scraper.name} から記事を収集開始 ===")
                articles = scraper.scrape_articles(articles_per_site)
                all_articles.extend(articles)
                
                # サイト間でのレート制限
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"{scraper.name} でエラー: {e}")
                continue
        
        logger.info(f"=== 全サイト収集完了: {len(all_articles)}件 ===")
        return all_articles
    
    def get_available_sources(self) -> List[str]:
        """利用可能なニュースソース一覧を取得"""
        return [scraper.name for scraper in self.scrapers]