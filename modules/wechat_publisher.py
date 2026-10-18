"""
微信公众号草稿箱推送模块
- 获取 access_token
- 将 Markdown 正文转为微信富文本 HTML
- 调用草稿接口推送文章
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Dict

import requests

logger = logging.getLogger(__name__)

WECHAT_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WECHAT_DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"

IMG_STYLE = 'style="display:block;width:100%;max-width:100%;margin:12px auto;border-radius:4px;"'

# access_token 缓存（进程内，7000秒内复用）
_token_cache: Dict = {"token": "", "expires_at": 0}


def get_access_token(app_id: str, app_secret: str) -> str:
    """获取微信 access_token，带缓存"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    resp = requests.get(WECHAT_TOKEN_URL, params={
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if "access_token" not in data:
        raise RuntimeError(f"获取 access_token 失败: {data}")

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 7200) - 200
    logger.info("access_token 获取成功")
    return _token_cache["token"]


# ─────────────────────────────────────────────
# Markdown → 微信友好 HTML
# ─────────────────────────────────────────────

def markdown_to_wechat_html(md: str) -> str:
    """
    将 Markdown 转换为微信公众号兼容的内联样式 HTML。
    微信不支持外链 CSS，所有样式必须内联。
    """
    html_lines = []

    # 颜色和字体配置
    H1_STYLE = 'style="font-size:22px;font-weight:bold;color:#1a1a1a;margin:20px 0 10px;border-left:4px solid #576CBC;padding-left:10px;"'
    H2_STYLE = 'style="font-size:18px;font-weight:bold;color:#2c3e50;margin:16px 0 8px;"'
    H3_STYLE = 'style="font-size:16px;font-weight:bold;color:#576CBC;margin:12px 0 6px;"'
    P_STYLE  = 'style="font-size:15px;line-height:1.9;color:#333;margin:8px 0;"'
    BQ_STYLE = ('style="border-left:4px solid #576CBC;padding:10px 16px;'
                'background:#f4f7fc;color:#576CBC;font-style:italic;margin:12px 0;font-size:15px;"')
    HR_STYLE = 'style="border:none;border-top:1px solid #e0e0e0;margin:16px 0;"'

    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # 标题
        if line.startswith("### "):
            html_lines.append(f'<h3 {H3_STYLE}>{line[4:].strip()}</h3>')
        elif line.startswith("## "):
            html_lines.append(f'<h2 {H2_STYLE}>{line[3:].strip()}</h2>')
        elif line.startswith("# "):
            html_lines.append(f'<h1 {H1_STYLE}>{line[2:].strip()}</h1>')

        # 引用块
        elif line.startswith("> "):
            html_lines.append(f'<blockquote {BQ_STYLE}>{line[2:].strip()}</blockquote>')

        # 分隔线
        elif re.match(r"^-{3,}$", line.strip()):
            html_lines.append(f'<hr {HR_STYLE}>')

        # 空行
        elif line.strip() == "":
            html_lines.append("")

        # 图片 ![alt](url)
        elif re.match(r"!\[.*?\]\(.+?\)", line.strip()):
            m = re.match(r"!\[(.*?)\]\((.+?)\)", line.strip())
            if m:
                alt, src = m.group(1), m.group(2)
                html_lines.append(f'<img src="{src}" alt="{alt}" {IMG_STYLE}>')

        # 普通段落
        else:
            text = line.strip()
            # 加粗
            text = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', text)
            # 斜体
            text = re.sub(r"\*(.+?)\*", r'<em>\1</em>', text)
            # 行内代码
            text = re.sub(r"`(.+?)`", r'<code style="background:#f0f0f0;padding:2px 4px;">\1</code>', text)
            # 链接
            text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
            if text:
                html_lines.append(f'<p {P_STYLE}>{text}</p>')

        i += 1

    return "\n".join(html_lines)


# ─────────────────────────────────────────────
# 推送草稿
# ─────────────────────────────────────────────

def push_to_draft(
    app_id: str,
    app_secret: str,
    title: str,
    content_html: str,
    author: str = "微信公众号自动化",
    digest: str = "",
    thumb_media_id: str = "",
) -> str:
    """
    将文章推送到微信公众号草稿箱。
    返回草稿 media_id。
    thumb_media_id 为空时不传该字段（避免 40007 错误）。
    """
    token = get_access_token(app_id, app_secret)

    article = {
        "title": title,
        "author": author,
        "digest": digest or title,
        "content": content_html,
        "content_source_url": "",
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }
    # thumb_media_id 必须是有效值，留空时不传该字段
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    payload = {"articles": [article]}

    resp = requests.post(
        f"{WECHAT_DRAFT_ADD_URL}?access_token={token}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()

    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"草稿推送失败: {result}")

    media_id = result.get("media_id", "")
    logger.info(f"草稿推送成功，media_id: {media_id}")
    return media_id


# ─────────────────────────────────────────────
# 一站式接口
# ─────────────────────────────────────────────

def publish_article_to_draft(
    app_id: str,
    app_secret: str,
    article: Dict,
) -> Dict:
    """
    接收 article_generator 的输出，自动配图、转换 HTML 并推送至草稿箱。
    返回结果摘要 dict。
    """
    title = article["title"]
    content_md = article["content"]

    # ── 1. 自动配图（将 [IMAGE: 关键词] 替换为微信图床图片）──
    token = get_access_token(app_id, app_secret)
    try:
        from image_uploader import process_article_images
        content_md = process_article_images(content_md, token)
    except Exception as e:
        logger.warning(f"自动配图失败，跳过：{e}")

    # ── 2. Markdown → 微信 HTML ──
    content_html = markdown_to_wechat_html(content_md)

    # ── 3. 生成摘要 ──
    plain = re.sub(r"[#*>`\[\]()-]", "", content_md).strip()
    digest = plain[:100].replace("\n", " ")

    media_id = push_to_draft(
        app_id, app_secret, title, content_html,
        digest=digest,
        thumb_media_id=article.get("thumb_media_id", ""),
    )

    return {
        "success": True,
        "title": title,
        "media_id": media_id,
        "pushed_at": datetime.now().isoformat(),
        "time_label": article.get("time_label", ""),
        "cover_prompt": article.get("cover_prompt", ""),
    }
