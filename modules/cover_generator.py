"""
封面图生成模块
使用 MiniMax image-01 模型生成封面，根据文章标题和 cover_prompt 自动生成不重复的封面。
失败时降级到 Unsplash 关键词搜图（每次关键词不同，不会重复）。
"""

import logging
import os
import re
import requests
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

COVERS_DIR = Path(__file__).parent / "covers"

# Saul Bass 风格提示词模板，根据文章内容填充
_PROMPT_TEMPLATE = (
    "Minimalist geometric poster in Saul Bass style, {topic}, "
    "{visual}, limited color palette of {colors}, "
    "screen print aesthetic, flat shapes, negative space, "
    "16:9 horizontal composition, bold iconic design, no text"
)

# 根据封面描述词提取关键视觉和配色
_VISUAL_DEFAULTS = [
    ("军事|防务|武器|战争|anduril|导弹", "dark steel fortress silhouette against navy sky", "navy blue, charcoal, orange"),
    ("AI|人工智能|科技|代码|算法|模型", "circuit board geometry dissolving into light beams", "deep blue, white, electric cyan"),
    ("金融|投资|股市|经济|货币|财富", "ascending geometric mountain graph", "forest green, cream, gold"),
    ("能源|石油|气候|碳|电力|太阳能", "industrial tower with radiant geometric sun", "burnt orange, dark brown, yellow"),
    ("医疗|生物|基因|药物|健康", "double helix rising from minimal horizon", "teal, white, coral"),
    ("政治|外交|地缘|国际|战略", "abstract globe with intersecting lines", "crimson, ivory, black"),
    ("创业|商业|企业|公司|品牌", "bold upward arrow breaking through geometric barrier", "cobalt blue, white, amber"),
]
_DEFAULT_VISUAL = ("abstract geometric shapes with dynamic tension", "steel blue, charcoal, warm white")


def _build_prompt(title: str, cover_prompt: str) -> str:
    """根据标题和封面描述词构建图像生成 prompt"""
    combined = f"{title} {cover_prompt}".lower()
    visual, colors = _DEFAULT_VISUAL
    for pattern, v, c in _VISUAL_DEFAULTS:
        if re.search(pattern, combined, re.IGNORECASE):
            visual, colors = v, c
            break
    topic = cover_prompt if cover_prompt else title[:40]
    return _PROMPT_TEMPLATE.format(topic=topic, visual=visual, colors=colors)


def _generate_via_minimax(prompt: str, output_path: str) -> bool:
    """调用 MiniMax image-01 生成封面图"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("未设置 OPENAI_API_KEY，跳过 MiniMax 图像生成")
        return False

    try:
        logger.info("调用 MiniMax image-01 生成封面...")
        resp = requests.post(
            "https://api.minimaxi.com/v1/image_generation",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "image-01",
                "prompt": prompt,
                "aspect_ratio": "16:9",
                "response_format": "url",
                "n": 1,
                "prompt_optimizer": True,
            },
            timeout=90,
        )
        data = resp.json()
        base = data.get("base_resp", {})
        if base.get("status_code") != 0:
            logger.warning(f"MiniMax 图像生成失败：{base}")
            return False

        urls = (data.get("data") or {}).get("image_urls", [])
        if not urls:
            logger.warning("MiniMax 未返回图片 URL")
            return False

        img_resp = requests.get(urls[0], timeout=30)
        if img_resp.status_code == 200 and len(img_resp.content) > 5000:
            with open(output_path, "wb") as f:
                f.write(img_resp.content)
            logger.info(f"MiniMax 封面生成成功：{output_path} ({len(img_resp.content)//1024} KB)")
            return True
        else:
            logger.warning(f"图片下载失败，状态码：{img_resp.status_code}")
            return False

    except Exception as e:
        logger.warning(f"MiniMax 图像生成异常：{e}")
        return False


def _generate_via_unsplash(title: str, output_path: str) -> bool:
    """降级：用文章关键词从 Unsplash 搜图（每次关键词不同，不会重复）"""
    # 提取2-3个关键词作为搜索词
    keywords_map = [
        ("军事|防务|武器|anduril", "military technology defense"),
        ("AI|人工智能|算法|模型", "artificial intelligence technology"),
        ("金融|投资|股市|经济", "finance investment economy"),
        ("能源|石油|气候|电力", "energy technology industrial"),
        ("医疗|生物|基因|健康", "medical science biology"),
        ("创业|商业|企业|品牌", "business startup innovation"),
    ]
    query = "technology future"
    for pattern, kw in keywords_map:
        if re.search(pattern, title, re.IGNORECASE):
            query = kw
            break

    try:
        url = f"https://source.unsplash.com/960x540/?{query.replace(' ', ',')}"
        resp = requests.get(url, timeout=20, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 10000:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            logger.info(f"Unsplash 封面下载成功（关键词：{query}）：{output_path}")
            return True
    except Exception as e:
        logger.warning(f"Unsplash 下载失败：{e}")
    return False


def generate_cover_with_fallback(title: str, cover_prompt: str, filename: str) -> str:
    """
    生成封面图，返回本地文件路径。
    优先 MiniMax AI 生成 → 失败则降级到 Unsplash 关键词搜图。
    """
    COVERS_DIR.mkdir(exist_ok=True)
    output_path = str(COVERS_DIR / filename)

    # 1. MiniMax image-01 生成
    prompt = _build_prompt(title, cover_prompt)
    logger.info(f"封面 prompt：{prompt[:80]}...")
    if _generate_via_minimax(prompt, output_path):
        return output_path

    # 2. 降级：Unsplash 关键词搜图（根据标题选关键词，不会每次一样）
    logger.info("降级到 Unsplash 封面图")
    if _generate_via_unsplash(title, output_path):
        return output_path

    # 3. 最终降级：默认封面
    default = Path(__file__).parent / "cover_default.jpg"
    if default.exists():
        logger.warning("使用默认封面（最终降级）")
        return str(default)

    return ""
