# 搜索引擎深度搜索指南

**仅包含国内可用的 7 个引擎。所有需要特殊网络环境的引擎（Google、DuckDuckGo、Yahoo、Ecosia、Qwant、WolframAlpha 等）和百度均已移除。**

---

## 🔍 必应（Bing）深度搜索

必应是国内用户最强通用搜索引擎，cn.bing.com 可直接访问。

### 高级搜索操作符

| 操作符 | 功能 | 示例 |
|--------|------|------|
| `site:` | 站内搜索 | `site:github.com python projects` |
| `filetype:` | 文件类型 | `filetype:pdf annual report` |
| `intitle:` | 标题包含 | `intitle:"machine learning" tutorial` |
| `inbody:` | 正文包含 | `inbody:password security` |
| `""` | 精确匹配 | `"machine learning"` |
| `-` | 排除关键词 | `python -snake` |
| `OR` | 或运算 | `machine learning OR deep learning` |
| `()` | 分组 | `(apple OR microsoft) phones` |

### 必应中文 vs 国际

| 模式 | URL | 适用场景 |
|------|-----|---------|
| 中文 | `cn.bing.com/search?q={kw}&ensearch=0` | 中文内容 |
| 国际 | `cn.bing.com/search?q={kw}&ensearch=1` | 英文/技术内容 |

### 搜索类型

| 类型 | 参数 | 示例 |
|------|------|------|
| 网页 | 默认 | `cn.bing.com/search?q=python` |
| 图片 | `/images/search?q=` | `cn.bing.com/images/search?q=landscape` |
| 新闻 | `/news/search?q=` | `cn.bing.com/news/search?q=AI` |
| 视频 | `/videos/search?q=` | `cn.bing.com/videos/search?q=tutorial` |

### 必应搜索示例

```javascript
// 1. GitHub 上的 Python 项目
web_fetch({"url": "https://cn.bing.com/search?q=site:github.com+python+machine+learning&ensearch=1"})

// 2. PDF 格式的技术文档
web_fetch({"url": "https://cn.bing.com/search?q=machine+learning+tutorial+filetype:pdf&ensearch=1"})

// 3. 排除特定网站
web_fetch({"url": "https://cn.bing.com/search?q=python+programming+-wikipedia&ensearch=1"})

// 4. 必应新闻
web_fetch({"url": "https://cn.bing.com/news/search?q=AI+breakthrough"})

// 5. 学术搜索（站内搜索 arxiv）
web_fetch({"url": "https://cn.bing.com/search?q=site:arxiv.org+transformer+architecture&ensearch=1"})

// 6. 公司财报 PDF
web_fetch({"url": "https://cn.bing.com/search?q=Microsoft+annual+report+2024+filetype:pdf&ensearch=1"})
```

---

## 🌍 综合搜索策略

### 按场景选择引擎

| 搜索目标 | 首选引擎 | 备选引擎 | 原因 |
|---------|---------|---------|------|
| 中文日常搜索 | 必应中文 | 360、搜狗 | 中文覆盖好 |
| 英文/技术搜索 | 必应国际 | 搜狗 | 英文内容覆盖好 |
| 微信公众号 | 微信搜索 | — | 唯一入口 |
| 新闻时事 | 头条搜索 | 必应中文 | 时效性强 |
| 金融投资 | 集思录 | — | 中文金融社区 |
| 学术研究 | 必应国际 | 必应站内搜索 arxiv | 学术内容 |

### 多引擎交叉验证

```javascript
// 同一关键词多引擎搜索，对比结果
web_fetch({"url": "https://cn.bing.com/search?q=AI+Agent+框架&ensearch=0"})
web_fetch({"url": "https://cn.bing.com/search?q=AI+Agent+framework&ensearch=1"})
web_fetch({"url": "https://sogou.com/web?query=AI+Agent+框架"})
```

### 专业领域搜索

```javascript
// GitHub 项目搜索（通过必应）
web_fetch({"url": "https://cn.bing.com/search?q=site:github.com+tensorflow+stars&ensearch=1"})

// Stack Overflow 问题（通过必应）
web_fetch({"url": "https://cn.bing.com/search?q=site:stackoverflow.com+python+memory+leak&ensearch=1"})

// arXiv 论文（通过必应）
web_fetch({"url": "https://cn.bing.com/search?q=site:arxiv.org+quantum+computing&ensearch=1"})
```

### URL 编码

搜索中文关键词时需要 URL 编码：
```javascript
web_fetch({"url": "https://cn.bing.com/search?q=" + encodeURIComponent("人工智能 教程") + "&ensearch=0"})
```
