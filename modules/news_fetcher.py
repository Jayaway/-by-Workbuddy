"""
新闻采集模块 - 从多个来源抓取最新资讯
"""

import logging
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _get(url: str, timeout: int = 10) -> requests.Response | None:
    """带错误处理的 GET 请求"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        logger.warning(f"请求失败 {url}: {e}")
        return None


# ─────────────────────────────────────────────
# 各来源采集函数
# ─────────────────────────────────────────────

def fetch_36kr() -> List[Dict]:
    """采集 36Kr 最新文章"""
    items = []
    resp = _get("https://36kr.com/")
    if not resp:
        return items
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select("a.article-item-title")[:10]:
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://36kr.com" + href
        if title and href:
            items.append({"source": "36Kr", "title": title, "url": href})
    return items


def fetch_hacker_news() -> List[Dict]:
    """采集 Hacker News 热门"""
    items = []
    resp = _get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not resp:
        return items
    story_ids = resp.json()[:15]
    for sid in story_ids:
        r = _get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if not r:
            continue
        d = r.json()
        if d.get("type") == "story" and d.get("title"):
            items.append({
                "source": "Hacker News",
                "title": d["title"],
                "url": d.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                "score": d.get("score", 0),
            })
        time.sleep(0.1)
    # 按热度排序
    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    return items[:8]


def fetch_techcrunch() -> List[Dict]:
    """采集 TechCrunch 最新文章（RSS）"""
    items = []
    resp = _get("https://techcrunch.com/feed/")
    if not resp:
        return items
    soup = BeautifulSoup(resp.text, "xml")
    for item in soup.find_all("item")[:8]:
        title = item.find("title")
        link = item.find("link")
        desc = item.find("description")
        if title and link:
            items.append({
                "source": "TechCrunch",
                "title": title.get_text(strip=True),
                "url": link.get_text(strip=True),
                "summary": BeautifulSoup(desc.get_text() if desc else "", "html.parser").get_text()[:200] if desc else "",
            })
    return items


def fetch_cls() -> List[Dict]:
    """采集财联社快讯（头条列表）"""
    items = []
    resp = _get("https://www.cls.cn/telegraph")
    if not resp:
        return items
    soup = BeautifulSoup(resp.text, "html.parser")
    for el in soup.select(".telegraph-content-box")[:10]:
        text = el.get_text(strip=True)
        if text:
            items.append({"source": "财联社", "title": text[:80], "url": "https://www.cls.cn/telegraph"})
    return items


def fetch_product_hunt() -> List[Dict]:
    """采集 Product Hunt 今日热门（RSS）"""
    items = []
    resp = _get("https://www.producthunt.com/feed")
    if not resp:
        return items
    soup = BeautifulSoup(resp.text, "xml")
    for item in soup.find_all("item")[:6]:
        title = item.find("title")
        link = item.find("link")
        if title and link:
            items.append({
                "source": "Product Hunt",
                "title": title.get_text(strip=True),
                "url": link.get_text(strip=True),
            })
    return items


# ─────────────────────────────────────────────
# 汇总入口
# ─────────────────────────────────────────────

def fetch_all_news() -> List[Dict]:
    """
    从所有来源抓取资讯，合并去重后返回。
    返回格式：[{"source": ..., "title": ..., "url": ..., "summary": ...}, ...]
    """
    logger.info("开始采集多源资讯...")
    all_items: List[Dict] = []

    fetchers = [
        ("36Kr",         fetch_36kr),
        ("Hacker News",  fetch_hacker_news),
        ("TechCrunch",   fetch_techcrunch),
        ("财联社",        fetch_cls),
        ("Product Hunt", fetch_product_hunt),
    ]

    for name, fn in fetchers:
        try:
            results = fn()
            logger.info(f"  {name}: 获取 {len(results)} 条")
            all_items.extend(results)
        except Exception as e:
            logger.error(f"  {name} 采集失败: {e}")
        time.sleep(random.uniform(0.5, 1.5))

    # 简单去重（标题相似）
    seen_titles = set()
    unique = []
    for item in all_items:
        key = item["title"][:20]
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(item)

    logger.info(f"采集完成，共 {len(unique)} 条去重后资讯")
    return unique
