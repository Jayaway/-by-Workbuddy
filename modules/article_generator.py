"""
文章生成模块 - 基于采集的资讯，调用 AI 生成"深度观察者"风格文章
使用 WorkBuddy 内置能力（subprocess 调用本地 AI）或 OpenAI 兼容 API
"""

import json
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 自动加载 .env 文件（如果存在）
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 系统提示词 - 深度观察者人设
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """你是微信公众号"深度观察者"的核心写手，拥有深厚投行背景的科技分析师。

【角色定位】
- 产业布道者与资本观察员
- 文风对标"巫师财经"：冷静、专业、叙事感强
- 善用宏大背景开场，以"降维打击"式的认知差拆解信息

【写作框架 - 四部曲】
1. 开篇：宏大叙事与范式背景（不直接说新闻，从行业大背景切入）
2. 中段：底层逻辑剥离
   - 资本链条：分析融资背后的推手，资本是想套现还是想重塑赛道？
   - 技术博弈：分析对上下游的"降维打击"能力
   - 地域适配：结合上海（张江/临港）或武汉（光谷）产业配套
3. 后段：认知输出与趋势判断（≥3个维度深度预判）
4. 结尾：以具有哲学高度的话收尾，保持"布道者"格调

【词汇库】存量博弈、护城河、马太效应、熵增、价值洼地、范式转移、降维打击

【排版要求】
- 重点观点加粗（**文字**）
- 核心金句用 > Blockquote
- 结构化小标题（## 一级、### 二级）
- 短段落，适合手机端阅读
- **在文章中合理插入 2-3 张配图占位符**，格式为：[IMAGE: 英文关键词]
  示例：[IMAGE: AI laboratory futuristic] 或 [IMAGE: stock market data]
  位置建议：开篇宏大叙事后、中段逻辑分析后、趋势判断前
- 文章末尾附：封面图 DALL-E 描述词

【硬性要求】
- 字数 ≥ 1500 字
- 严禁虚构事实，数据需注明来源
- 严禁投资建议（结尾标注：以上分析不构成投资建议）
- 严禁营销话术和政治评论
- 自动过滤公关通稿赞美辞令，只保留事实、数据、关键人物语录"""


ARTICLE_PROMPT_TEMPLATE = """
【今日资讯摘要】
{news_summary}

【历史选题（过去7天，请勿重复）】
{history_topics}

【本次任务】
时段标签：{time_label}
请基于以上资讯，选取 1-2 个最具深度价值的议题，撰写一篇符合"深度观察者"风格的公众号文章。

输出格式：
---TITLE---
（文章标题，20字以内，有冲击力）
---CONTENT---
（正文，Markdown格式，≥1500字）
---COVER_IMAGE_PROMPT---
（封面图DALL-E 3生成描述词，英文，50字以内）
---END---
"""


# ─────────────────────────────────────────────
# 调用 AI 生成文章
# ─────────────────────────────────────────────

def _call_ai(prompt: str) -> str:
    """
    调用 AI 生成文章内容。
    优先 Claude（Anthropic） → 降级 MiniMax（OpenAI 兼容）→ 本地 ollama
    """
    # 方式1：Claude（优先）
    claude_key = os.environ.get("CLAUDE_API_KEY")
    claude_model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-6-thinking")
    if claude_key:
        try:
            import anthropic as _anthropic_mod
            client = _anthropic_mod.Anthropic(api_key=claude_key)
            # thinking 模型用 extended_thinking，普通模型走普通路径
            if "thinking" in claude_model:
                resp = client.messages.create(
                    model=claude_model,
                    max_tokens=16000,
                    thinking={"type": "enabled", "budget_tokens": 10000},
                    messages=[{"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{prompt}"}],
                )
                # 只取 text 类型的 block，过滤掉 thinking block
                return "\n".join(
                    b.text for b in resp.content if b.type == "text"
                )
            else:
                resp = client.messages.create(
                    model=claude_model,
                    max_tokens=8000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.content[0].text
        except ImportError:
            logger.warning("anthropic 包未安装，降级到 MiniMax...")
        except Exception as e:
            logger.warning(f"Claude 调用失败（{e}），降级到 MiniMax...")

    # 方式2：MiniMax / OpenAI 兼容 API（降级）
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY")
    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model = os.environ.get("AI_MODEL", "gpt-4o")

    if api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key, base_url=api_base)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.85,
                max_tokens=4000,
            )
            return resp.choices[0].message.content
        except ImportError:
            logger.warning("openai 包未安装，尝试 ollama...")
        except Exception as e:
            logger.error(f"MiniMax API 调用失败: {e}")
            raise

    # 方式2：本地 ollama
    try:
        result = subprocess.run(
            ["ollama", "run", "qwen2.5:14b"],
            input=f"{SYSTEM_PROMPT}\n\n{prompt}",
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            return result.stdout
        logger.error(f"ollama 返回错误: {result.stderr}")
    except FileNotFoundError:
        logger.warning("ollama 未安装")
    except Exception as e:
        logger.error(f"ollama 调用失败: {e}")

    raise RuntimeError(
        "未找到可用的 AI 后端。\n"
        "请设置环境变量 OPENAI_API_KEY（及可选的 OPENAI_API_BASE、AI_MODEL），\n"
        "或本地安装 ollama 并拉取模型（ollama pull qwen2.5:14b）。"
    )


def _parse_ai_output(raw: str) -> Dict:
    """解析 AI 输出，提取标题、正文、封面描述词"""
    # 先过滤 <think> 思考链（兜底，_call_ai 返回前已处理一次）
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    title = ""
    content = ""
    cover_prompt = ""

    m = re.search(r"---TITLE---\s*(.*?)\s*---CONTENT---", raw, re.DOTALL)
    if m:
        title = m.group(1).strip()

    m = re.search(r"---CONTENT---\s*(.*?)\s*---COVER_IMAGE_PROMPT---", raw, re.DOTALL)
    if m:
        content = m.group(1).strip()

    m = re.search(r"---COVER_IMAGE_PROMPT---\s*(.*?)\s*---END---", raw, re.DOTALL)
    if m:
        cover_prompt = m.group(1).strip()

    # fallback：如果解析失败，整段作为正文
    if not content:
        content = raw.strip()
    if not title:
        title = f"深度观察 · {datetime.now().strftime('%Y-%m-%d')}"

    return {"title": title, "content": content, "cover_prompt": cover_prompt}


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def generate_article(
    news_items: List[Dict],
    history_topics: List[str],
    time_label: str = "晚间深度",
    content_type: str = None
) -> Dict:
    """
    根据资讯列表生成一篇深度文章。
    content_type: 可选，指定内容类型 (tech/finance/local_life/growth/lifestyle)
    返回：{"title": ..., "content": ..., "cover_prompt": ..., "generated_at": ...}
    """
    # 根据内容类型调整 prompt
    content_type_hints = {
        "tech": "聚焦科技数码、AI、数码新品、工具推荐",
        "finance": "聚焦财经理财、存钱、副业、理财入门",
        "local_life": "聚焦上海本地生活、探店、租房、通勤攻略",
        "growth": "聚焦青年成长、求职、职场进阶、社交",
        "lifestyle": "轻松生活方式、影视推荐、周末活动"
    }
    content_hint = content_type_hints.get(content_type, "") if content_type else ""
    # 构建资讯摘要
    news_lines = []
    for i, item in enumerate(news_items[:20], 1):
        line = f"{i}. [{item['source']}] {item['title']}"
        if item.get("url"):
            line += f" ({item['url']})"
        if item.get("summary"):
            line += f"\n   摘要：{item['summary'][:100]}"
        news_lines.append(line)
    news_summary = "\n".join(news_lines) if news_lines else "（暂无资讯，请基于行业趋势自行发挥）"

    history_str = "\n".join(f"- {t}" for t in history_topics) if history_topics else "（无历史选题）"

    # 添加内容类型提示到 prompt
    content_directive = f"\n\n【内容方向】{content_hint}" if content_hint else ""
    
    prompt = ARTICLE_PROMPT_TEMPLATE.format(
        news_summary=news_summary,
        history_topics=history_str,
        time_label=time_label,
    ) + content_directive

    logger.info(f"调用 AI 生成文章（时段：{time_label}）...")

    # 最多重试 3 次，确保标题不与历史重复
    for attempt in range(3):
        raw = _call_ai(prompt)
        # 过滤 <think> 思考链（MiniMax 等模型会输出）
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        parsed = _parse_ai_output(raw)

        # 检查标题是否与历史重复（关键词重叠超过 60% 视为重复）
        new_title = parsed.get("title", "")
        is_dup = False
        for old_title in history_topics:
            # 提取关键词：去停用词后的字符集合
            new_words = set(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", new_title))
            old_words = set(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", old_title))
            if not new_words or not old_words:
                continue
            overlap = len(new_words & old_words) / min(len(new_words), len(old_words))
            if overlap >= 0.6:
                logger.warning(f"标题疑似重复（第{attempt+1}次）：《{new_title}》≈《{old_title}》（重叠率{overlap:.0%}），重新生成...")
                is_dup = True
                # 在 prompt 里强制追加排除指令
                prompt += f"\n\n⚠️ 注意：标题《{new_title}》与已发内容《{old_title}》重复，请选择完全不同的议题重新生成。"
                break

        if not is_dup:
            break
    else:
        logger.warning("3次重试后仍疑似重复，使用最后一次结果")

    parsed["generated_at"] = datetime.now().isoformat()
    parsed["time_label"] = time_label

    logger.info(f"文章生成完成：《{parsed['title']}》({len(parsed['content'])} 字)")
    return parsed
