#!/usr/bin/env python3
"""
孙宇晨音频系列 - 自动发布流水线
================================================
功能：
  1. 扫描音频目录，找到下一期未处理的 MP3
  2. 用 faster-whisper 本地转写（或复用已有 TXT）
  3. 用 AI 根据转写稿提炼生成公众号文章
  4. 上传统一系列封面（带期数水印）
  5. 推送到微信公众号草稿箱
  6. 同步到知乎 + 雪球草稿
  7. 记录进度，打印剩余期数

用法：
  python3.11 sun_pipeline.py            # 发布下一期
  python3.11 sun_pipeline.py --dry-run  # 只生成，不推送
  python3.11 sun_pipeline.py --ep 007   # 指定期号
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ── 路径 ──────────────────────────────────────
BASE_DIR = Path(__file__).parent
AUDIO_DIR = Path("/Users/vv/Downloads/孙宇晨音频")
TRANSCRIPT_DIR = BASE_DIR / "sun_transcripts"
DRAFT_DIR = BASE_DIR / "sun_drafts"
PROGRESS_FILE = BASE_DIR / "sun_progress.json"
COVER_SRC = None  # 封面原图路径，启动时动态查找

# 自动加载 .env
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BASE_DIR))
from config import WECHAT_APP_ID, WECHAT_APP_SECRET
from wechat_publisher import get_access_token, push_to_draft, markdown_to_wechat_html
from audio_manager import get_audio_media_id

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────
# 006 是第1期（已发布），007 起从第2期开始
EP_OFFSET = 5   # ep_num(006) - 1 = 5，所以 期数 = int(ep_str) - EP_OFFSET
FIRST_EP = "006"
ALREADY_PUBLISHED = {"006"}   # 已发布的期号集合


# ════════════════════════════════════════════════
# 1. 扫描音频目录
# ════════════════════════════════════════════════

def scan_audio_files() -> list[dict]:
    """扫描并返回所有音频文件信息，按期号排序"""
    files = []
    for f in sorted(AUDIO_DIR.glob("*.mp3")):
        m = re.match(r"^(\d{3})", f.name)
        if m:
            ep_str = m.group(1)
            ep_num = int(ep_str) - EP_OFFSET  # 006→1, 007→2, ...
            # 清理标题：去掉售后微信号等干扰信息
            title_raw = f.stem
            title_clean = re.sub(r"\[售后[：:].+?\]", "", title_raw).strip()
            title_clean = re.sub(r"^\d{3}", "", title_clean).strip()
            # 去掉【xxx】标签只保留核心标题
            title_clean = re.sub(r"^【[^】]+】", "", title_clean).strip()
            if not title_clean:
                title_clean = title_raw
            files.append({
                "ep_str": ep_str,
                "ep_num": ep_num,
                "filename": f.name,
                "path": str(f),
                "title_raw": title_clean,
            })
    return files


def get_next_episode(progress: dict) -> Optional[dict]:
    """找到下一期未发布的音频"""
    published = set(progress.get("published", list(ALREADY_PUBLISHED)))
    all_files = scan_audio_files()
    for ep in all_files:
        if ep["ep_str"] not in published:
            return ep
    return None


def get_episode_by_str(ep_str: str) -> Optional[dict]:
    """按期号字符串查找"""
    for ep in scan_audio_files():
        if ep["ep_str"] == ep_str:
            return ep
    return None


# ════════════════════════════════════════════════
# 2. 音频转写
# ════════════════════════════════════════════════

def transcribe_audio(audio_path: str, ep_str: str) -> str:
    """
    转写音频为文字。
    优先复用已有 TXT（原 Buzz 转写或本次转写缓存）。
    """
    TRANSCRIPT_DIR.mkdir(exist_ok=True)

    # 先找原始 Buzz 转写文件
    for f in AUDIO_DIR.glob(f"{ep_str}*.txt"):
        logger.info(f"复用已有转写文件：{f.name}")
        return f.read_text(encoding="utf-8")

    # 检查缓存
    cache_file = TRANSCRIPT_DIR / f"{ep_str}.txt"
    if cache_file.exists():
        logger.info(f"复用转写缓存：{cache_file.name}")
        return cache_file.read_text(encoding="utf-8")

    # 本地 faster-whisper 转写
    logger.info(f"开始转写 {Path(audio_path).name}（本地 Whisper base 模型）...")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, language="zh", beam_size=2)
        text = "".join([seg.text for seg in segments])
        # 缓存到本地
        cache_file.write_text(text, encoding="utf-8")
        logger.info(f"转写完成，共 {len(text)} 字，已缓存到 {cache_file.name}")
        return text
    except ImportError:
        raise RuntimeError("未安装 faster-whisper，请运行：python3.11 -m pip install faster-whisper")


# ════════════════════════════════════════════════
# 3. AI 生成文章
# ════════════════════════════════════════════════

ARTICLE_PROMPT = """你是一位擅长从音频访谈中提炼思想精华的内容作者，文风犀利、有观点、有深度。

以下是一段音频的转写文稿，来自"孙宇晨·财富自由革命之路"系列，这是第 {ep_num} 期，音频标题是《{title_raw}》。

【转写文稿】
{transcript}

【任务】
请根据以上内容，写一篇适合微信公众号发布的深度文章，要求：
1. 标题：根据核心观点提炼，要有冲击力和话题感，不要用"孙宇晨说"这类标题
2. 正文：2000-3000字，结构清晰（用 ## 二级标题划分），不要逐字转述，而是提炼观点、加入分析和延伸
3. 文章开头加一段引言，点明这期的核心议题
4. 文章结尾加一段总结，升华主题
5. 语言风格：口语化但有深度，适合30岁左右的读者
6. 在文章最开头（标题前）加上：🎧 本期音频：第 {ep_num} 期·{title_raw}

输出格式要求：
- 第一行：# 文章标题（这行必须有，用 # 开头）
- 空一行
- 然后是正文内容
只输出文章（Markdown 格式），不要输出任何解释、说明或思考过程。
"""

def generate_article(transcript: str, ep_num: int, title_raw: str, audio_path: str, ep_str: str) -> dict:
    """调用 AI 生成公众号文章，并在标题前插入音频播放标签"""
    import openai
    client = openai.OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_API_BASE"),
    )
    model = os.environ.get("AI_MODEL", "MiniMax-M2.5")

    # 转写稿太长时截取前 8000 字（MiniMax 上下文限制）
    transcript_trimmed = transcript[:8000]
    if len(transcript) > 8000:
        transcript_trimmed += "\n\n[...原文较长，已截取前8000字...]"

    prompt = ARTICLE_PROMPT.format(
        ep_num=ep_num,
        title_raw=title_raw,
        transcript=transcript_trimmed,
    )

    logger.info(f"调用 AI 生成文章（ep {ep_num}）...")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.7,
    )
    content = resp.choices[0].message.content.strip()

    # 去掉 <think>...</think> 内容（MiniMax 思考链）
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # 提取标题：优先找 # 开头的行
    lines = content.splitlines()
    title = ""
    content_lines = []
    found_title = False
    for line in lines:
        if not found_title and line.startswith("# "):
            title = line[2:].strip()
            found_title = True
            continue
        content_lines.append(line)

    if found_title:
        content = "\n".join(content_lines).strip()
    else:
        # 没有 # 标题，尝试从正文第一段提取
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and len(stripped) > 5 and len(stripped) < 60:
                title = stripped
                break
    if not title:
        title = f"第{ep_num}期·{title_raw}"

    # 获取音频 media_id
    audio_media_id = get_audio_media_id(ep_str)
    audio_filename = Path(audio_path).name

    if audio_media_id:
        # 插入音频播放标签（使用微信素材库中的音频）
        audio_section = (
            f"🎧 **本期音频**：第 {ep_num} 期·{title_raw}\n\n"
            f'<audio data-wxmusici="{audio_media_id}" controls></audio>\n\n'
            f"---\n\n"
        )
    else:
        # 降级：只显示文件名
        audio_section = (
            f"🎧 **本期音频**：第 {ep_num} 期·{title_raw}\n\n"
            f"> **音频文件**：`{audio_filename}`\n\n"
            f"---\n\n"
        )

    # 将音频部分插入到内容开头
    content = audio_section + f"# {title}\n\n" + content

    logger.info(f"文章生成完成：《{title}》（{len(content)} 字）")
    return {
        "title": title,
        "content": content,
        "ep_str": "",  # 后续填入
        "ep_num": ep_num,
    }


# ════════════════════════════════════════════════
# 4. 封面处理（统一封面，加期数）
# ════════════════════════════════════════════════

def find_cover_image() -> Optional[Path]:
    """查找系列封面原图"""
    candidates = [
        Path("/Users/vv/Pictures/孙宇晨.JPG"),  # 用户指定的新封面
        Path("/Users/vv/Pictures/微信公众号.png"),  # 备用封面
        Path("/Users/vv/Downloads/公众号封面.png"),
        Path("/Users/vv/Downloads/公众号封面.jpg"),
        BASE_DIR / "sun_cover.png",
        BASE_DIR / "sun_cover.jpg",
    ]
    for p in candidates:
        if p.exists():
            return p
    # 模糊搜索
    for p in Path("/Users/vv/Downloads").iterdir():
        if "封面" in p.name and p.suffix.lower() in (".png", ".jpg", ".jpeg"):
            return p
    return None


def prepare_cover(ep_num: int, cover_src: Optional[Path]) -> Optional[Path]:
    """直接使用封面原图，不加期数水印"""
    if cover_src is None:
        logger.warning("未找到系列封面图，将使用默认封面")
        return None

    # 直接使用原图，不做任何处理
    logger.info(f"使用封面原图：{cover_src.name}")
    return cover_src


def upload_cover_to_wechat(cover_path: Path) -> str:
    """上传封面到微信素材库，返回 thumb_media_id"""
    from upload_cover import upload_thumb
    media_id = upload_thumb(str(cover_path))
    logger.info(f"封面上传成功：{media_id}")
    return media_id


# ════════════════════════════════════════════════
# 5. 推送微信
# ════════════════════════════════════════════════

def push_to_wechat(article: dict, thumb_media_id: str = "") -> dict:
    """推送文章到微信草稿箱"""
    from wechat_publisher import get_access_token
    from image_uploader import process_article_images

    token = get_access_token(WECHAT_APP_ID, WECHAT_APP_SECRET)

    # 图片占位符处理
    content_md = article["content"]
    try:
        content_md = process_article_images(content_md, token)
    except Exception as e:
        logger.warning(f"自动配图失败：{e}")

    content_html = markdown_to_wechat_html(content_md)
    plain = re.sub(r"[#*>`\[\]()-]", "", content_md).strip()
    digest = plain[:100].replace("\n", " ")

    media_id = push_to_draft(
        WECHAT_APP_ID, WECHAT_APP_SECRET,
        article["title"], content_html,
        author="深度观察者",
        digest=digest,
        thumb_media_id=thumb_media_id,
    )
    return {"success": True, "media_id": media_id, "title": article["title"]}


# ════════════════════════════════════════════════
# 6. 进度管理
# ════════════════════════════════════════════════

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"published": list(ALREADY_PUBLISHED)}


def save_progress(progress: dict, ep_str: str, title: str, media_id: str):
    published = set(progress.get("published", []))
    published.add(ep_str)
    progress["published"] = sorted(published)
    progress.setdefault("records", []).append({
        "ep_str": ep_str,
        "title": title,
        "media_id": media_id,
        "pushed_at": datetime.now().isoformat(),
    })
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def print_remaining(progress: dict):
    published = set(progress.get("published", []))
    all_eps = scan_audio_files()
    remaining = [e for e in all_eps if e["ep_str"] not in published]
    total = len(all_eps)
    done = total - len(remaining)
    print(f"\n📊 进度：已发 {done} 期 / 共 {total} 期，剩余 {len(remaining)} 期可发")
    if remaining:
        print(f"   下一期：{remaining[0]['ep_str']} 《{remaining[0]['title_raw']}》（第 {remaining[0]['ep_num']} 期）")


# ════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════

def run(ep_str: Optional[str] = None, dry_run: bool = False):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # 创建目录
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    DRAFT_DIR.mkdir(exist_ok=True)

    # 加载进度
    progress = load_progress()

    # 确定本期
    if ep_str:
        ep = get_episode_by_str(ep_str)
        if not ep:
            print(f"❌ 未找到期号 {ep_str} 的音频文件")
            sys.exit(1)
    else:
        ep = get_next_episode(progress)
        if not ep:
            print("✅ 所有期已发布完毕！")
            print_remaining(progress)
            return

    print(f"\n{'='*60}")
    print(f"本期：{ep['ep_str']} 《{ep['title_raw']}》  第 {ep['ep_num']} 期")
    print(f"{'='*60}")

    # Step 1: 转写
    logger.info("Step 1: 音频转写")
    transcript = transcribe_audio(ep["path"], ep["ep_str"])
    print(f"✅ 转写完成，{len(transcript)} 字")

    # Step 2: 生成文章
    logger.info("Step 2: AI 生成文章")
    article = generate_article(transcript, ep["ep_num"], ep["title_raw"], ep["path"], ep["ep_str"])
    article["ep_str"] = ep["ep_str"]

    # 保存草稿
    draft_path = DRAFT_DIR / f"ep{ep['ep_str']}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    draft_path.write_text(f"# {article['title']}\n\n{article['content']}", encoding="utf-8")
    print(f"✅ 文章生成：《{article['title']}》（{len(article['content'])} 字）")
    print(f"   草稿已保存：{draft_path.name}")

    if dry_run:
        print(f"\n[dry-run] 跳过推送")
        print_remaining(progress)
        return

    # Step 3: 封面
    logger.info("Step 3: 准备封面")
    cover_src = find_cover_image()
    if cover_src:
        print(f"✅ 找到封面原图：{cover_src.name}")
    else:
        print(f"⚠️  未找到封面原图，将使用默认封面")

    cover_path = prepare_cover(ep["ep_num"], cover_src)
    thumb_media_id = ""
    if cover_path:
        try:
            thumb_media_id = upload_cover_to_wechat(cover_path)
            print(f"✅ 封面上传成功")
        except Exception as e:
            logger.warning(f"封面上传失败：{e}")
            # 使用已有默认封面
            thumb_media_id = os.environ.get("WECHAT_THUMB_MEDIA_ID", "")
    else:
        thumb_media_id = os.environ.get("WECHAT_THUMB_MEDIA_ID", "")

    # Step 4: 推送微信
    logger.info("Step 4: 推送微信草稿")
    result = push_to_wechat(article, thumb_media_id)
    print(f"✅ 微信草稿推送成功：{result['media_id']}")

    # Step 5: 同步知乎/雪球（已禁用，用户手动同步）
    # 2026-03-15 用户取消自动同步功能
    logger.info("Step 5: 同步知乎/雪球（已禁用）")
    print("⚠️  知乎/雪球同步已禁用，请手动同步")

    # Step 6: 记录进度
    save_progress(progress, ep["ep_str"], article["title"], result["media_id"])

    # Step 7: 打印剩余
    progress_updated = load_progress()
    print_remaining(progress_updated)

    print(f"\n请到微信公众号草稿箱发布：《{article['title']}》")


# ════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="孙宇晨系列自动发布")
    parser.add_argument("--ep", type=str, help="指定期号，如 007")
    parser.add_argument("--dry-run", action="store_true", help="只生成，不推送")
    args = parser.parse_args()
    run(ep_str=args.ep, dry_run=args.dry_run)
