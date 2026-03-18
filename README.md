# 微信公众号自动发布工具

自动化抓取科技资讯、AI 生成文章并推送到微信公众号草稿箱。

## 项目结构

```
wechat-bot/
├── config.py              # 主配置文件
├── main.py                # 主入口（定时任务）
├── article_generator.py  # AI 文章生成
├── wechat_publisher.py    # 微信 API 推送
├── news_fetcher.py        # 资讯采集
├── cover_generator.py     # 封面图生成
├── image_uploader.py      # 图片上传
├── sun_pipeline.py        # 孙宇晨系列自动发布
├── drafts/                # 草稿目录
├── covers/                # 封面图目录
├── history/               # 发布历史
└── logs/                  # 日志目录
```

## 环境配置

### 1. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填写你的配置：

```bash
cp .env.example .env
```

### 3. 微信公众号设置

1. 登录微信公众号后台：https://mp.weixin.qq.com/
2. 获取 AppID 和 AppSecret
3. **IP 白名单**：将服务器 IP 添加到白名单
4. 上传封面图，获取 thumb_media_id

## 使用方法

### 方式一：定时自动发布

配置 WorkBuddy 自动化任务：

```bash
# 早报（每天 8:00）
cd /path/to/wechat-bot && python3 main.py --slot morning

# 午报（每天 12:00）
cd /path/to/wechat-bot && python3 main.py --slot noon

# 晚报（每天 19:00）
cd /path/to/wechat-bot && python3 main.py --slot evening
```

### 方式二：手动发布单篇文章

```bash
# 生成并推送早报
python3 main.py --slot morning
```

### 方式三：孙宇晨系列发布

```bash
# 发布下一期
python3 sun_pipeline.py
```

## 配置说明

### config.py 关键配置

```python
# 微信公众号凭证
WECHAT_APP_ID = "your_app_id"
WECHAT_APP_SECRET = "your_app_secret"
WECHAT_THUMB_MEDIA_ID = "your_thumb_media_id"

# 内容源
SOURCES = {
    "深度": ["https://theblockbeats.info/", "https://36kr.com/"],
    "信息差": ["https://news.ycombinator.com/"],
    "政策": ["https://www.shanghai.gov.cn/"],
}

# AI 配置（选择其一）
OPENAI_API_KEY = "your_openai_key"      # OpenAI
MINIMAX_API_KEY = "your_minimax_key"    # MiniMax
```

## 常见问题

### Q: 推送失败，提示 40101 或 41002？
A: 检查 AppID/AppSecret 是否正确，IP 是否在白名单。

### Q: 封面图上传失败？
A: 检查图片大小（< 2MB），格式支持 jpg/png。

### Q: AI 生成超时？
A: 网络问题或 API 限流，代码已实现 Claude → MiniMax 自动降级。

## 许可证

MIT License
