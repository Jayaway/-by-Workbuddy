"""
封面图获取模块
从外网免费图库 Picsum（https://picsum.photos）按关键词确定性取图，
无需 API Key、无需 AI 生成，也不依赖已下线/加了人机校验的图库。
"""

import hashlib
import logging
import re
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

COVERS_DIR = Path(__file__).parent / "covers"

# 关键词 → 英文搜索词映射（用于生成确定性的图片种子）
_KEYWORD_MAP = [
    ("军事|防务|武器|战争|anduril|导弹", "military defense war"),
    ("AI|人工智能|科技|代码|算法|模型", "artificial intelligence technology"),
    ("金融|投资|股市|经济|货币|财富", "finance stock market"),
    ("能源|石油|气候|碳|电力|太阳能", "energy solar power"),
    ("医疗|生物|基因|药物|健康", "medical science biology"),
    ("政治|外交|地缘|国际|战略", "politics geopolitics"),
    ("创业|商业|企业|公司|品牌", "business startup"),
]
_DEFAULT_KEYWORDS = "technology future"


def _pick_keywords(title: str, cover_prompt: str) -> str:
    """根据标题和封面描述词挑选英文关键词"""
    combined = f"{title} {cover_prompt}"
    for pattern, kw in _KEYWORD_MAP:
        if re.search(pattern, combined, re.IGNORECASE):
            return kw
    return _DEFAULT_KEYWORDS


def _seed_of(text: str) -> str:
    """由关键词生成稳定的种子（同一选题 → 同一封面，不同选题 → 不同封面）"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def _download(url: str, output_path: str, min_bytes: int = 10000) -> bool:
    """下载图片到本地，校验状态码和文件大小"""
    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > min_bytes:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            logger.info(f"封面下载成功：{output_path} ({len(resp.content)//1024} KB)")
            return True
        logger.warning(f"下载失败：状态码 {resp.status_code}，大小 {len(resp.content)} 字节")
    except Exception as e:
        logger.warning(f"下载异常：{e}")
    return False


def _fetch_via_picsum(keywords: str, output_path: str) -> bool:
    """Picsum 确定性取图（按关键词种子）"""
    seed = _seed_of(keywords)
    return _download(f"https://picsum.photos/seed/{seed}/960/540", output_path)


def _fetch_via_picsum_random(output_path: str) -> bool:
    """Picsum 随机图（最终降级，无关键词）"""
    return _download("https://picsum.photos/960/540", output_path)


def generate_cover_with_fallback(title: str, cover_prompt: str, filename: str) -> str:
    """
    从外网免费图库抓取封面图，返回本地文件路径。
    顺序：Picsum 关键词确定性图 → Picsum 随机图 → 默认封面。
    """
    COVERS_DIR.mkdir(exist_ok=True)
    output_path = str(COVERS_DIR / filename)

    keywords = _pick_keywords(title, cover_prompt)
    logger.info(f"从外网图库抓取封面（关键词：{keywords}）")

    if _fetch_via_picsum(keywords, output_path):
        return output_path

    logger.info("Picsum 关键词取图失败，降级随机图")
    if _fetch_via_picsum_random(output_path):
        return output_path

    default = Path(__file__).parent / "cover_default.jpg"
    if default.exists():
        logger.warning("使用默认封面（最终降级）")
        return str(default)

    return ""
