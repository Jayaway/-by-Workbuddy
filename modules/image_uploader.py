"""
图片配图模块 - 为文章自动配图并上传到微信图床
流程：关键词 → Unsplash 抓取 → 上传到微信永久素材 → 返回微信 CDN URL
"""

import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# 微信上传图片到图文消息素材接口（返回 URL，可直接嵌入 content）
WECHAT_UPLOAD_IMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"

# Unsplash 免费图片（不需要 API Key，直接通过 source.unsplash.com 随机取图）
UNSPLASH_SOURCE = "https://source.unsplash.com/featured/900x500/?{keywords}"

# 备用：Picsum（纯随机，无关键词）
PICSUM_URL = "https://picsum.photos/900/500?random={seed}"


def fetch_image_bytes(keyword: str, index: int = 0) -> Optional[bytes]:
    """
    按关键词从 Unsplash 抓取一张图片，返回原始字节。
    失败时返回 None。
    """
    # 关键词转英文（简单映射）
    kw_en = _translate_keyword(keyword)
    url = UNSPLASH_SOURCE.format(keywords=quote(kw_en))

    try:
        resp = requests.get(url, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 10000:
            logger.info(f"图片抓取成功：{keyword} ({len(resp.content)//1024}KB)")
            return resp.content
    except Exception as e:
        logger.warning(f"Unsplash 抓取失败 ({keyword}): {e}")

    # fallback：picsum 随机图
    try:
        seed = abs(hash(keyword)) % 1000 + index
        resp = requests.get(PICSUM_URL.format(seed=seed), timeout=15, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 10000:
            logger.info(f"使用 Picsum 备用图片 (seed={seed})")
            return resp.content
    except Exception as e:
        logger.warning(f"Picsum 备用也失败: {e}")

    return None


def upload_image_to_wechat(access_token: str, image_bytes: bytes, filename: str = "image.jpg") -> Optional[str]:
    """
    将图片上传到微信图文消息素材（uploadimg 接口），返回微信 CDN URL。
    注意：这个接口返回的是可直接嵌入 content 的 URL，不是 media_id。
    """
    try:
        resp = requests.post(
            f"{WECHAT_UPLOAD_IMG_URL}?access_token={access_token}",
            files={"media": (filename, image_bytes, "image/jpeg")},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        url = result.get("url")
        if url:
            logger.info(f"图片上传成功：{url}")
            return url
        logger.warning(f"上传返回异常: {result}")
    except Exception as e:
        logger.error(f"上传图片失败: {e}")
    return None


def process_article_images(content_md: str, access_token: str) -> str:
    """
    扫描 Markdown 中的 [IMAGE: 关键词] 占位符，
    抓取对应图片上传至微信，替换为真实的 Markdown 图片语法。
    返回处理后的 Markdown。
    """
    pattern = re.compile(r'\[IMAGE:\s*([^\]]+)\]')
    placeholders = pattern.findall(content_md)

    if not placeholders:
        logger.info("文章中未找到图片占位符 [IMAGE: ...]，跳过配图")
        return content_md

    logger.info(f"发现 {len(placeholders)} 个图片占位符，开始配图...")

    def replace_placeholder(match):
        keyword = match.group(1).strip()
        img_bytes = fetch_image_bytes(keyword)
        if img_bytes is None:
            logger.warning(f"无法获取图片 ({keyword})，移除占位符")
            return ""  # 移除失败的占位符

        wechat_url = upload_image_to_wechat(access_token, img_bytes)
        if wechat_url:
            return f"\n![{keyword}]({wechat_url})\n"
        else:
            logger.warning(f"图片上传失败 ({keyword})，移除占位符")
            return ""

        # 避免频率限制
        time.sleep(0.5)

    result = pattern.sub(replace_placeholder, content_md)
    return result


def _translate_keyword(kw: str) -> str:
    """
    简单的中文关键词 → 英文映射，提升 Unsplash 搜索效果。
    """
    mapping = {
        "AI": "artificial intelligence technology",
        "人工智能": "artificial intelligence",
        "科技": "technology innovation",
        "资本": "finance investment",
        "融资": "startup funding",
        "芯片": "semiconductor chip",
        "数据": "data analytics",
        "云计算": "cloud computing",
        "机器人": "robot automation",
        "无人驾驶": "autonomous vehicle",
        "马斯克": "elon musk tech",
        "xAI": "artificial intelligence lab",
        "代码": "programming code",
        "创业": "startup entrepreneur",
        "上海": "shanghai skyline",
        "武汉": "wuhan city",
        "光谷": "technology park",
        "张江": "shanghai zhangjiang",
        "投资": "investment finance",
        "大模型": "large language model AI",
        "ChatGPT": "AI chatbot interface",
        "产业": "industry factory",
        "逻辑图": "data flow diagram chart",
        "架构": "architecture diagram",
    }
    for zh, en in mapping.items():
        if zh in kw:
            return en
    # 如果没匹配到，原样返回（英文关键词本身就有效）
    return kw
