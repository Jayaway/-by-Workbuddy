"""
音频管理模块
查找指定期号的音频文件并上传到微信公众号永久素材库（type=voice），
返回 media_id，供文章中 <audio> 播放标签使用。
"""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

WECHAT_MATERIAL_ADD_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"

# 音频文件所在目录（按需修改）
AUDIO_DIR = Path("/Users/vv/Downloads/孙宇晨音频")


def get_audio_media_id(ep_str: str) -> str:
    """查找指定期号音频并上传到微信素材库，返回 media_id；失败返回空字符串"""
    from config import WECHAT_APP_ID, WECHAT_APP_SECRET
    from wechat_publisher import get_access_token

    audio_path = None
    for pattern in (f"{ep_str}*.mp3", f"{ep_str}*.m4a", f"{ep_str}*.wav"):
        matches = sorted(AUDIO_DIR.glob(pattern))
        if matches:
            audio_path = matches[0]
            break

    if audio_path is None:
        logger.warning(f"未找到期号 {ep_str} 的音频文件")
        return ""

    token = get_access_token(WECHAT_APP_ID, WECHAT_APP_SECRET)
    with open(audio_path, "rb") as f:
        resp = requests.post(
            f"{WECHAT_MATERIAL_ADD_URL}?access_token={token}&type=voice",
            files={"media": (audio_path.name, f)},
            timeout=120,
        )

    data = resp.json()
    media_id = data.get("media_id", "")
    if media_id:
        logger.info(f"音频上传成功：{media_id}")
    else:
        logger.warning(f"音频上传失败：{data}")
    return media_id
