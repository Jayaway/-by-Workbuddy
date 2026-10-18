#!/usr/bin/env python3
"""
微信公众号自动化 - 主调度脚本
用法：
  python3 main.py                   # 立即执行一次（自动判断当前时段）
  python3 main.py --slot morning    # 指定时段：morning / noon / evening
  python3 main.py --dry-run         # 只生成文章，不推送微信
  python3 main.py --mock            # 测试模式：跳过 AI，用模拟数据验证流程
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

# ── 路径设置 ──────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "modules"))

# 自动加载 .env 文件（含 WECHAT_THUMB_MEDIA_ID 等配置）
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from config import (
    WECHAT_APP_ID, WECHAT_APP_SECRET, __version__,
    SCHEDULE_LABELS, HISTORY_FILE, LOG_DIR, DRAFT_DIR, DEDUP_DAYS
)
from news_fetcher import fetch_all_news
from article_generator import generate_article
from wechat_publisher import publish_article_to_draft
from history_manager import get_recent_topics, append_record
from cover_generator import generate_cover_with_fallback
from upload_cover import upload_thumb


# ── 日志配置 ──────────────────────────────────
def setup_logging(slot: str) -> None:
    log_dir = BASE_DIR / LOG_DIR
    log_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"{today}_{slot}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def detect_slot() -> str:
    """根据当前小时自动判断时段"""
    hour = datetime.now().hour
    if hour < 10:
        return "morning"
    elif hour < 15:
        return "noon"
    else:
        return "evening"


def save_draft_locally(article: Dict, slot: str) -> str:
    """将文章保存到本地 drafts 目录"""
    draft_dir = BASE_DIR / DRAFT_DIR
    draft_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = draft_dir / f"{ts}_{slot}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {article['title']}\n\n")
        f.write(f"> 时段：{article.get('time_label', '')}  |  生成时间：{article.get('generated_at', '')}\n\n")
        f.write(article["content"])
        if article.get("cover_prompt"):
            f.write(f"\n\n---\n**封面图描述词（DALL-E 3）：**\n{article['cover_prompt']}\n")
    return str(filename)


def main():
    parser = argparse.ArgumentParser(description="微信公众号自动化 - 自动发文机器人")
    parser.add_argument("--slot", choices=["morning", "noon", "evening"],
                        help="指定运行时段（默认自动判断）")
    parser.add_argument("--content-type", 
                        choices=["tech", "finance", "local_life", "growth", "lifestyle"],
                        help="内容类型：tech-科技数码, finance-财经理财, local_life-本地生活, growth-青年成长, lifestyle-综合")
    parser.add_argument("--dry-run", action="store_true",
                        help="只生成文章到本地，不推送微信草稿箱")
    parser.add_argument("--mock", action="store_true",
                        help="测试模式：跳过 AI 调用，用模拟内容验证整体流程")
    args = parser.parse_args()

    slot = args.slot or detect_slot()
    time_label = SCHEDULE_LABELS.get(slot, "晚间深度")

    setup_logging(slot)
    logger = logging.getLogger("main")
    logger.info(f"========== 微信公众号自动化 v{__version__} 启动 | 时段：{time_label} ==========")

    # 1. 采集资讯
    news_items = fetch_all_news()
    if not news_items:
        logger.warning("资讯采集为空，将基于行业趋势生成文章")

    # 2. 读取历史选题（去重用）
    history_file = str(BASE_DIR / HISTORY_FILE)
    recent_topics = get_recent_topics(history_file, days=DEDUP_DAYS)
    logger.info(f"过去{DEDUP_DAYS}天历史选题：{len(recent_topics)} 条")

    # 3. 生成文章
    if args.mock:
        logger.info("[mock 模式] 使用模拟文章，跳过 AI 调用")
        article = {
            "title": f"【测试】深度观察 · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": (
                "## 范式转移前夜：一场关于智能基础设施的存量博弈\n\n"
                "在 AI 泡沫消散后的第三年，产业正悄然完成从「玩具」到「工具」的底层基座重构。\n\n"
                "### 资本链条\n\n**头部玩家的护城河**正在悄然加深。\n\n"
                "> 真正的竞争壁垒，从来不在产品层，而在数据飞轮与算力基础设施的马太效应。\n\n"
                "### 技术博弈\n\n上海张江与武汉光谷，作为两大产业极，正在经历截然不同的熵增路径。\n\n"
                "### 趋势预判\n\n**维度一：** 存量博弈将替代增量扩张，成为 2026 年主旋律。\n\n"
                "**维度二：** 价值洼地将出现在垂直行业 AI 与本地化部署方向。\n\n"
                "**维度三：** 地方产业配套政策将成为下一波定价权争夺的关键变量。\n\n"
                "---\n\n*以上分析不构成投资建议。*\n\n"
                "*历史不会重演，但总会押韵——而押韵的规律，永远藏在资本的流向里。*\n"
            ),
            "cover_prompt": "Minimalist tech cityscape at dusk, Shanghai Zhangjiang district, neon blue and gold tones, cinematic",
            "generated_at": datetime.now().isoformat(),
            "time_label": time_label,
        }
    else:
        article = generate_article(news_items, recent_topics, time_label, args.content_type)

    # 注入封面图 media_id（从 .env 读取）
    if not article.get("thumb_media_id"):
        article["thumb_media_id"] = os.environ.get("WECHAT_THUMB_MEDIA_ID", "")

    # 4. 保存本地草稿
    local_path = save_draft_locally(article, slot)
    logger.info(f"本地草稿已保存：{local_path}")

    # 5. 生成封面图（Mondo AI → 降级 Unsplash）并上传到微信素材库
    if not (args.dry_run or args.mock):
        logger.info("正在生成封面图...")
        from datetime import datetime as _dt
        cover_filename = f"cover_{_dt.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cover_path = generate_cover_with_fallback(
            title=article.get("title", ""),
            cover_prompt=article.get("cover_prompt", ""),
            filename=cover_filename,
        )
        if cover_path:
            try:
                new_media_id = upload_thumb(cover_path)
                article["thumb_media_id"] = new_media_id
                logger.info(f"封面图上传成功，media_id: {new_media_id}")
            except Exception as e:
                logger.warning(f"封面图上传失败，使用默认封面：{e}")
        else:
            logger.warning("封面图生成失败，使用默认封面")

    # 6. 推送到微信草稿箱
    if args.dry_run or args.mock:
        mode_tag = "[mock 模式]" if args.mock else "[dry-run 模式]"
        logger.info(f"{mode_tag} 跳过微信推送")
        print(f"\n{'='*60}")
        print(f"文章标题：{article['title']}")
        print(f"字数：{len(article['content'])} 字")
        print(f"本地文件：{local_path}")
        if article.get("cover_prompt"):
            print(f"封面图描述词：{article['cover_prompt']}")
        print(f"{'='*60}\n")
        return

    result = publish_article_to_draft(WECHAT_APP_ID, WECHAT_APP_SECRET, article)
    logger.info(f"推送结果：{result}")
    # 7. 记录历史
    append_record(history_file, result)

    print(f"\n完成！")
    print(f"   标题：{result['title']}")
    print(f"   media_id：{result['media_id']}")
    print(f"   请登录公众号后台 → 草稿箱 → 确认后发布")
    if result.get("cover_prompt"):
        print(f"\n封面图建议（可用 DALL-E 3 生成）：\n   {result['cover_prompt']}")

    # 发送系统通知（Mac + iPhone 同一 Apple ID 会同步收到）
    import subprocess
    title_text = result['title']
    subprocess.run([
        "osascript", "-e",
        f'display notification "草稿已推送，请前往各平台发布" with title "微信公众号自动化" subtitle "{title_text}"'
    ], capture_output=True)

    # 8. 同步到知乎 & 雪球（已禁用，用户手动同步）
    # 2026-03-15 用户取消自动同步功能
    print(f"\n{'='*60}")
    print(f"⚠️  知乎/雪球同步已禁用，请手动同步")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
