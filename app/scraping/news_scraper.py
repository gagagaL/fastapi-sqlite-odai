import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
import re
from urllib.parse import urljoin, urlparse
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NewsArticle:
    """ニュース記事データ"""
    title: str
    content: str
    url: str
    source: str

class NewsScraperBase:
    """ニューススクレイパーの基底クラス"""
    
    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        """記事リンクを取得（サブクラスで実装）"""
        raise NotImplementedError
    
    def scrape_article(self, url: str) -> Optional[NewsArticle]:
        """単一記事をスクレイピング（サブクラスで実装）"""
        raise NotImplementedError
    
    def scrape_articles(self, max_articles: int = 5) -> List[NewsArticle]:
        """複数記事をスクレイピング"""
        articles = []
        links = self.get_article_links(max_articles * 2)  # 余裕を持って取得
        
        for i, link in enumerate(links[:max_articles]):
            try:
                logger.info(f"📰 記事取得中 ({i+1}/{max_articles}): {link}")
                article = self.scrape_article(link)
                if article:
                    articles.append(article)
                time.sleep(1)  # 負荷軽減
            except Exception as e:
                logger.warning(f"⚠️ 記事取得失敗: {link} - {e}")
                continue
        
        logger.info(f"✅ {len(articles)}件の記事を取得完了")
        return articles

class YahooNewsScraper(NewsScraperBase):
    """Yahoo!ニューススクレイパー"""
    
    def __init__(self):
        super().__init__("Yahoo!ニュース", "https://news.yahoo.co.jp")
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        """Yahoo!ニュースの記事リンクを取得"""
        try:
            # トップページから記事リンクを取得
            response = self.session.get(f"{self.base_url}/topics")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # 記事リンクを抽出（パターン1: トピックス）
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
            logger.error(f"❌ Yahoo!ニュース記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[NewsArticle]:
        """Yahoo!ニュース記事をスクレイピング"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            # 本文取得
            content_selectors = [
                '[data-cl-params*="body"]',
                '.articleMain',
                '.hbody',
                'div[class*="article"]',
                'div[class*="body"]'
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
            
            if len(content) < 50:  # 短すぎる場合は無効
                logger.warning(f"⚠️ コンテンツが短すぎます: {url}")
                return None
            
            return NewsArticle(
                title=title,
                content=content,
                url=url,
                source=self.source_name
            )
            
        except Exception as e:
            logger.error(f"❌ 記事スクレイピングエラー: {url} - {e}")
            return None

class NHKNewsScraper(NewsScraperBase):
    """NHKニューススクレイパー"""
    
    def __init__(self):
        super().__init__("NHK", "https://www3.nhk.or.jp")
    
    def get_article_links(self, max_links: int = 10) -> List[str]:
        """NHKニュースの記事リンクを取得"""
        try:
            response = self.session.get(f"{self.base_url}/news/")
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
            logger.error(f"❌ NHKニュース記事リンク取得エラー: {e}")
            return []
    
    def scrape_article(self, url: str) -> Optional[NewsArticle]:
        """NHKニュース記事をスクレイピング"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # タイトル取得
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            # 本文取得
            content_elem = soup.find('div', class_='module--detail-content') or \
                          soup.find('div', class_='body-text') or \
                          soup.find('section', class_='module--detail-content')
            
            if content_elem:
                content = content_elem.get_text(strip=True)
            else:
                # フォールバック
                paragraphs = soup.find_all('p')
                content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if len(content) < 50:
                logger.warning(f"⚠️ コンテンツが短すぎます: {url}")
                return None
            
            return NewsArticle(
                title=title,
                content=content,
                url=url,
                source=self.source_name
            )
            
        except Exception as e:
            logger.error(f"❌ 記事スクレイピングエラー: {url} - {e}")
            return None