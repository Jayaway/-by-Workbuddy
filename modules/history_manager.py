"""
历史发布记录管理模块
- 记录已发布选题
- 读取近期选题用于去重（避免重复推送相似话题）
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def get_recent_topics(history_file: str, days: int = 7) -> List[str]:
    """读取近 N 天内的历史选题标题列表（用于去重）"""
    path = Path(history_file)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"读取历史记录失败：{e}")
        return []

    records = data if isinstance(data, list) else data.get("records", [])
    cutoff = datetime.now() - timedelta(days=days)
    topics = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        title = rec.get("title") or rec.get("topic", "")
        if not title:
            continue
        ts = rec.get("pushed_at") or rec.get("time", "")
        try:
            if ts and datetime.fromisoformat(ts) < cutoff:
                continue
        except Exception:
            pass  # 时间解析失败则默认纳入
        topics.append(title)
    return topics


def append_record(history_file: str, result: dict) -> None:
    """追加一条发布记录到历史文件"""
    path = Path(history_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = []

    if isinstance(data, dict):
        data = data.get("records", [])
    if not isinstance(data, list):
        data = []

    data.append({
        "title": result.get("title", ""),
        "media_id": result.get("media_id", ""),
        "pushed_at": result.get("pushed_at", datetime.now().isoformat()),
    })
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"历史记录已更新：{path}")
