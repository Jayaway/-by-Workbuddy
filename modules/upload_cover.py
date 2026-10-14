"""
封面上传模块
将封面图上传到微信公众号永久素材库（type=thumb），返回 thumb_media_id。
供草稿接口的 thumb_media_id 参数使用。
"""

import logging
import os
import requests

logger = logging.getLogger(__name__)

WECHAT_MATERIAL_ADD_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"


def upload_thumb(image_path: str) -> str:
    """上传封面图到微信永久素材库，返回 thumb_media_id"""
    from config import WECHAT_APP_ID, WECHAT_APP_SECRET
    from wechat_publisher import get_access_token

    token = get_access_token(WECHAT_APP_ID, WECHAT_APP_SECRET)

    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{WECHAT_MATERIAL_ADD_URL}?access_token={token}&type=thumb",
            files={"media": (os.path.basename(image_path), f, "image/jpeg")},
            timeout=60,
        )

    data = resp.json()
    media_id = data.get("media_id", "")
    if not media_id:
        raise RuntimeError(f"封面上传失败：{data}")

    logger.info(f"封面上传成功，thumb_media_id：{media_id}")
    return media_id
