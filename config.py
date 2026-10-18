# ============================================================
# 微信公众号自动化 - 配置文件模板
# ============================================================

# 项目版本号
__version__ = "1.1.1"

import os
# AI 后端配置（二选一）：
#
# 方式1：设置环境变量（推荐，不要把 key 写死在代码里）
#   export MINIMAX_API_KEY="your_api_key"
#   export MINIMAX_GROUP_ID="your_group_id"
#
# 方式2：写入 .env 文件（项目根目录），脚本启动时自动加载
#   MINIMAX_API_KEY=your_api_key
#   MINIMAX_GROUP_ID=your_group_id
#
# 方式3：使用 OpenAI/Claude（需要配置对应环境变量）
#   OPENAI_API_KEY=your_openai_key
#   ANTHROPIC_API_KEY=your_anthropic_key
# ============================================================

# 微信公众号凭证（从微信公众号后台获取）
# 登录 https://mp.weixin.qq.com/ -> 设置与开发 -> 基本配置
# 优先从环境变量 / .env 读取，避免把密钥提交到仓库
WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "your_wechat_app_id")
WECHAT_APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "your_wechat_app_secret")

# 封面图素材 ID（需要先上传封面图到微信公众号素材库获取）
# 在公众号后台：新建图文消息 -> 上传封面 -> 获取 media_id
WECHAT_THUMB_MEDIA_ID = os.environ.get("WECHAT_THUMB_MEDIA_ID", "your_thumb_media_id")

# 公众号名称
ACCOUNT_NAME = "微信公众号自动化"

# 调度时间（本地时间）
SCHEDULE_TIMES = {
    "morning": "08:00",   # 早报视角
    "noon":    "12:00",   # 午间复盘
    "evening": "19:00",   # 晚间深度
}

# 各时段对应的风格标签
SCHEDULE_LABELS = {
    "morning": "早报视角",
    "noon":    "午间复盘",
    "evening": "晚间深度",
}

# 内容采集源（可自定义添加）
SOURCES = {
    "深度": [
        "https://theblockbeats.info/",   # 律动（区块链/AI/硬科技）
        "https://36kr.com/",              # 36氪（科技创投）
        "https://www.cls.cn/",            # 财联社（财经）
    ],
    "信息差": [
        "https://news.ycombinator.com/",  # Hacker News（极客社区）
        "https://techcrunch.com/",        # TechCrunch（国际科技）
        "https://www.producthunt.com/",   # Product Hunt（新产品）
    ],
    "政策": [
        "https://www.shanghai.gov.cn/",   # 上海市政府
        "https://www.zghg.com.cn/",       # 武汉东湖高新区
        "https://www.ndrc.gov.cn/",        # 国家发改委
    ],
}

# 文章最低字数
MIN_ARTICLE_LENGTH = 1500

# 历史去重天数（7天内不重复推送相似话题）
DEDUP_DAYS = 7

# 历史记录文件
HISTORY_FILE = "history/published.json"

# 日志目录
LOG_DIR = "logs"

# 草稿目录
DRAFT_DIR = "drafts"
