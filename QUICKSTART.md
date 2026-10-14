# 🚀 快速启动指南

## 获取完整项目包

项目已打包在以下目录：

```
/Users/vv/WorkBuddy/Claw/export/wechat-publisher/
```

包含以下文件：

| 文件 | 说明 |
|------|------|
| `config.py` | 配置文件模板 |
| `main.py` | 主入口 |
| `modules/` | 核心模块 |
| `requirements.txt` | Python 依赖 |
| `.env.example` | 环境变量模板 |
| `README.md` | 完整文档 |

---

## 部署步骤

### 1️⃣ 复制项目到目标服务器

```bash
# 在目标服务器上
cd /path/to/your/project
git clone https://github.com/Jayaway/-by-Workbuddy.git
cd -by-Workbuddy
```

或直接复制文件夹。

### 2️⃣ 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的配置
nano .env
```

必须配置：
- `WECHAT_APP_ID` - 微信公众号 AppID
- `WECHAT_APP_SECRET` - 微信公众号 AppSecret
- `WECHAT_THUMB_MEDIA_ID` - 封面图 media_id
- `MINIMAX_API_KEY` - MiniMax API Key（用于 AI 生成）

### 3️⃣ 安装依赖

```bash
pip3 install -r requirements.txt
```

### 4️⃣ 测试运行

```bash
# 生成早报并推送
python3 main.py --slot morning
```

---

## 常见问题

### Q: 如何获取 WECHAT_THUMB_MEDIA_ID？
1. 登录微信公众号后台
2. 新建图文消息
3. 上传封面图片
4. 在素材库中查看图片，获取 media_id

### Q: AI 生成失败怎么办？
- 检查 API Key 是否正确
- 网络是否可达
- 代码已实现自动降级（Claude → MiniMax）

### Q: 推送失败，提示 IP 不在白名单？
- 将服务器公网 IP 添加到微信公众号后台的 IP 白名单

---

## 文件说明

### 核心模块

| 模块 | 功能 |
|------|------|
| `main.py` | 主入口，调度文章生成和推送 |
| `modules/article_generator.py` | AI 文章生成（支持 Claude/MiniMax） |
| `modules/wechat_publisher.py` | 微信公众号 API 封装 |
| `modules/news_fetcher.py` | 资讯采集爬虫 |
| `modules/cover_generator.py` | 封面图（外网免费图库 Picsum 抓取，无需 AI） |
| `modules/image_uploader.py` | 图片上传到微信图床 |
| `modules/sun_pipeline.py` | 孙宇晨系列音频转文章工作流 |

---

## 定时任务配置

### macOS / Linux crontab

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天 8:00、12:00、19:00）
0 8 * * * cd /path/to/wechat-bot && python3 main.py --slot morning >> logs/morning.log 2>&1
0 12 * * * cd /path/to/wechat-bot && python3 main.py --slot noon >> logs/noon.log 2>&1
0 19 * * * cd /path/to/wechat-bot && python3 main.py --slot evening >> logs/evening.log 2>&1
```

### WorkBuddy 自动化

在 WorkBuddy 客户端创建自动化任务，参考上面的命令。
