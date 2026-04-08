# bilibili-mcp

B站自动化工具

基于 bilibili-api-python，实现视频上传、动态发布、直播弹幕、收藏夹管理、关注粉丝等全功能自动化操作。

---

## 功能特性

| 类别 | 功能 |
|------|------|
| 📤 内容发布 | 上传视频、发布动态（图文/纯文字）、定时发布 |
| 🔍 搜索 | 搜索视频、搜索用户 |
| 🔥 热门 | 热门视频、分区排行榜、每周必看 |
| 👍 互动 | 点赞、投币、收藏、评论、回复评论 |
| 💬 弹幕 | 获取视频弹幕、发送弹幕 |
| 📺 直播 | 查看直播间、发送直播弹幕 |
| 📁 收藏夹 | 查看/创建收藏夹、管理收藏内容 |
| 👥 社交 | 关注/取关用户、查看粉丝列表 |
| 📜 历史 | 查看观看历史、清空历史 |

---

## 安装

```bash
bash scripts/install.sh
```

安装脚本会：
1. 检查 Python 版本（需要 3.9+）
2. 安装 Python 依赖
3. 检查 ffmpeg（可选，用于视频封面提取）
4. 创建数据目录

### 可选依赖

- **ffmpeg**：用于从视频提取封面（推荐）
  - macOS: `brew install ffmpeg`
  - Ubuntu: `sudo apt install ffmpeg`
  - Windows: `choco install ffmpeg`

---

## 凭据存储

登录凭据使用 **加密文件** 存储在 `data/credential.enc` 中（Fernet AES-128-CBC），密钥自动从机器指纹派生，无需手动管理。

- 向后兼容旧格式（`credential.json` / `.zshrc` 环境变量），首次加载时自动迁移
- `cryptography` 库不可用时回退到权限受限的 JSON 文件（chmod 600）

---

## 扫码登录流程

当 `check_login` 返回未登录时：

1. 调用 `get_login_qrcode`
2. 二维码图片会**自动弹出预览窗口**（macOS 用 `open` 命令）
3. 函数会**自动轮询等待扫码**（每 3 秒检查一次，最长 120 秒）
4. 用户扫码确认后，凭据自动加密保存，返回登录成功
5. 如果超时，提示用户重新调用

**备用方案**：如果自动轮询中断，可手动调用 `check_qrcode_status` 检查状态

---

## 调用方式

所有操作通过 `bili_call.py` 脚本：

```bash
python3 scripts/bili_call.py <tool_name> [json_args]
```

---

## 工具列表

### 📋 账号管理

| 工具 | 说明 | 参数 |
|------|------|------|
| `check_login` | 检查登录状态 | 无 |
| `get_login_qrcode` | 获取登录二维码 | 无 |
| `check_qrcode_status` | 检查扫码状态 | 无 |
| `logout` | 退出登录 | 无 |

### 📤 内容发布

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `upload_video` | 上传视频 | `video_path`, `title`, `tid`(分区ID) |
| `publish_dynamic` | 发布动态 | `text` |
| `delete_dynamic` | 删除动态 | `dynamic_id` |

**upload_video 可选参数**：
- `cover`: 封面图片路径（不填会自动从视频提取）
- `desc`: 视频简介
- `tags`: 标签列表，如 `["游戏","实况"]`
- `dynamic`: 动态文字
- `original`: 是否原创，默认 true
- `source`: 转载来源（非原创时必填）

**publish_dynamic 可选参数**：
- `images`: 图片路径列表
- `topic_id`: 话题ID
- `schedule_time`: 定时发布时间（ISO8601格式）

**常用分区 tid**：
| tid | 分区 | tid | 分区 |
|-----|------|-----|------|
| 17 | 单机游戏 | 171 | 电子竞技 |
| 172 | 手机游戏 | 138 | 搞笑 |
| 21 | 日常 | 75 | 动物圈 |
| 183 | 影视杂谈 | 182 | 影视剪辑 |
| 122 | 野生技术协会 | 39 | 演讲公开课 |

### 🔍 搜索

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `search_video` | 搜索视频 | `keyword` |
| `search_user` | 搜索用户 | `keyword` |

可选：`page`(页码，默认1)

### 🔥 热门/排行榜

| 工具 | 说明 | 参数 |
|------|------|------|
| `get_hot_videos` | 获取热门视频 | `pn`(页码) |
| `get_rank` | 获取排行榜 | `tid`(分区), `day`(3或7天) |
| `get_weekly_hot` | 每周必看 | 无 |

**排行榜 tid**：0=全站, 1=动画, 3=音乐, 4=游戏, 5=娱乐, 36=科技, 160=生活, 181=影视

### 📺 视频信息

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `get_video_info` | 获取视频详情 | `bvid` |
| `get_user_info` | 获取用户信息 | `mid` |
| `get_user_videos` | 获取用户投稿 | `mid` |

**get_user_videos 可选**：`page`, `order`(pubdate/click/stow)

### 👍 视频互动

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `like_video` | 点赞/取消 | `bvid` |
| `coin_video` | 投币 | `bvid` |
| `favorite_video` | 收藏 | `bvid` |
| `comment_video` | 评论 | `bvid`, `text` |
| `get_video_comments` | 获取评论 | `bvid` |
| `reply_comment` | 回复评论 | `bvid`, `rpid`, `text` |

**可选参数**：
- `like_video`: `unlike=true` 取消点赞
- `coin_video`: `num`(投币数量，1或2)
- `favorite_video`: `add_media_ids`(收藏夹ID列表)

### 💬 弹幕

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `get_video_danmaku` | 获取弹幕 | `bvid` |
| `send_video_danmaku` | 发送弹幕 | `bvid`, `text` |

**send_video_danmaku 可选**：`dm_time`(出现时间秒数)

### 📝 动态

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `like_dynamic` | 点赞动态 | `dynamic_id` |
| `repost_dynamic` | 转发动态 | `dynamic_id` |
| `get_my_dynamics` | 我的动态 | 无 |
| `get_user_dynamics` | 用户动态 | `mid` |

### 📺 直播

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `get_live_info` | 直播间信息 | `room_id` |
| `get_live_area_list` | 直播分区列表 | 无 |
| `get_live_list` | 直播列表 | 无 |
| `send_live_danmaku` | 发送直播弹幕 | `room_id`, `text` |

**get_live_list 可选**：`area_id`(分区ID), `page`

### 📁 收藏夹

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `get_my_favorite_list` | 我的收藏夹 | 无 |
| `get_favorite_content` | 收藏夹内容 | `media_id` |
| `create_favorite_folder` | 创建收藏夹 | `title` |

**create_favorite_folder 可选**：`intro`, `privacy`(是否私密)

### 👥 关注/粉丝

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `follow_user` | 关注/取关 | `mid` |
| `get_my_followings` | 我的关注 | 无 |
| `get_my_followers` | 我的粉丝 | 无 |

**follow_user 可选**：`unfollow=true` 取消关注

### 📜 历史记录

| 工具 | 说明 | 参数 |
|------|------|------|
| `get_history` | 观看历史 | `page`, `max_count` |
| `clear_history` | 清空历史 | 无 |

---

## 示例

```bash
# 检查登录
python3 scripts/bili_call.py check_login

# 搜索视频
python3 scripts/bili_call.py search_video '{"keyword":"AI教程"}'

# 获取热门视频
python3 scripts/bili_call.py get_hot_videos

# 获取游戏区排行榜
python3 scripts/bili_call.py get_rank '{"tid":4,"day":7}'

# 获取视频信息
python3 scripts/bili_call.py get_video_info '{"bvid":"BV1xx411c7mD"}'

# 点赞视频
python3 scripts/bili_call.py like_video '{"bvid":"BV1xx411c7mD"}'

# 发送弹幕
python3 scripts/bili_call.py send_video_danmaku '{"bvid":"BV1xx411c7mD","text":"666"}'

# 获取直播间信息
python3 scripts/bili_call.py get_live_info '{"room_id":21452505}'

# 发布动态
python3 scripts/bili_call.py publish_dynamic '{"text":"今天天气不错"}'

# 发布带图动态
python3 scripts/bili_call.py publish_dynamic '{"text":"分享图片","images":["/path/to/img.jpg"]}'

# 上传视频
python3 scripts/bili_call.py upload_video '{"video_path":"/path/to/video.mp4","title":"我的视频","tid":17,"desc":"视频简介","tags":["游戏","实况"]}'

# 关注用户
python3 scripts/bili_call.py follow_user '{"mid":123456}'

# 创建收藏夹
python3 scripts/bili_call.py create_favorite_folder '{"title":"我的收藏","privacy":true}'
```

---

## 约束

- 视频标题 ≤ 80 字
- 动态文字 ≤ 2000 字
- 弹幕 ≤ 100 字
- 每日投稿上限约 50 个
- 封面会自动从视频提取（需要 ffmpeg 或 opencv-python）
- 部分操作需要登录（会自动提示）

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 未登录 | 执行扫码登录流程 |
| 凭据过期 | 调用 `logout` 后重新登录 |
| 凭据迁移 | 旧版凭据会在首次加载时自动迁移到加密存储 |
| 视频上传失败 | 检查文件路径、分区ID是否正确 |
| 封面提取失败 | 安装 ffmpeg: `brew install ffmpeg` |
| 操作被风控 | 降低操作频率，等待一段时间后重试 |

---

## 文件结构

```
bilibili-mcp/
├── SKILL.md              # OpenClaw 技能描述文件
├── README.md             # 使用说明（本文件）
├── requirements.txt      # Python 依赖
├── .gitignore           # Git 忽略规则
├── scripts/
│   ├── bili_call.py       # 主调用脚本（39个工具）
│   ├── credential_store.py # 凭据加密存储模块
│   ├── bili_login.py      # 交互式登录脚本
│   ├── bili_login_step.py # 分步登录脚本
│   └── install.sh         # 安装脚本
└── data/
    └── .gitkeep         # 数据目录占位
```

---

## 信息

- **版本**: 1.3.0
- **依赖**: bilibili-api-python >= 17.0.0, cryptography >= 41.0.0
- **Python**: >= 3.9

---

## 许可

MIT License
