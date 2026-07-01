# 🎬 Douyin Knowledge Hub

> 抖音视频学习与知识库系统

## 📌 项目简介

通过监控指定抖音账号的分享视频，自动获取内容、分析总结、构建个人知识库。

## 🎯 核心目标

1. **自动化采集**：监控抖音小号，自动获取分享的视频
2. **智能分析**：使用 AI 分析视频内容，生成摘要和学习笔记
3. **知识沉淀**：构建可搜索、可查询的个人知识库
4. **持续学习**：长期维护，不断积累技术知识

## 🔄 工作流程

```
大号（用户）→ 分享视频 → 小号（系统监控）→ 获取内容 → AI 分析 → 知识库
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────┐
│            Douyin Knowledge Hub              │
├─────────────────────────────────────────────┤
│                                              │
│  Layer 1: 数据采集层                         │
│  ─────────────────────                       │
│  • 监控抖音小号分享视频                       │
│  • 使用 Douyin_TikTok_Download_API            │
│  • 获取视频元数据（标题、描述、标签）          │
│  • 定时轮询，检测新视频                       │
│                                              │
│  Layer 2: 内容理解层                         │
│  ─────────────────────                       │
│  • AI 分析视频描述和标题                      │
│  • 提取技术关键词和概念                       │
│  • 生成内容摘要                               │
│  • （可选）语音转文字                         │
│                                              │
│  Layer 3: 知识存储层                         │
│  ─────────────────────                       │
│  • SQLite 结构化存储                          │
│  • 字段：视频ID、标题、摘要、标签、笔记        │
│  • 支持全文搜索                               │
│  • 支持按标签分类                             │
│                                              │
│  Layer 4: 智能交互层                         │
│  ─────────────────────                       │
│  • 基于知识库问答                             │
│  • 技术趋势分析                               │
│  • 学习进度追踪                               │
│  • 定期学习报告                               │
│                                              │
└─────────────────────────────────────────────┘
```

## 📋 功能清单

### Phase 1: 基础功能（MVP）

- [ ] 部署抖音数据采集服务
- [ ] 实现小号视频监控
- [ ] 获取视频元数据
- [ ] AI 内容分析和摘要
- [ ] 本地知识库存储

### Phase 2: 增强功能

- [ ] 语音转文字（Whisper）
- [ ] 视频截图分析
- [ ] 知识图谱构建
- [ ] 语义搜索

### Phase 3: 智能功能

- [ ] 学习进度追踪
- [ ] 个性化推荐
- [ ] 定期学习报告
- [ ] 技术趋势分析

## 🛠️ 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| **数据采集** | Douyin_TikTok_Download_API | 开源抖音爬虫 |
| **后端服务** | Python + FastAPI | 轻量级 API |
| **AI 分析** | MiMo API | 内容理解和摘要 |
| **数据库** | SQLite | 轻量级存储 |
| **语音转文字** | Whisper（可选） | 本地语音识别 |
| **定时任务** | Cron | 定时监控 |

## 📊 资源需求

### 服务器配置

| 资源 | 需求 | 当前状态 |
|------|------|----------|
| **CPU** | 2 核 | ✅ 满足 |
| **内存** | 1 GiB | ✅ 满足 |
| **磁盘** | 1 GiB/年 | ✅ 满足 |
| **网络** | 稳定 | ✅ 满足 |

### 成本估算

| 项目 | 成本 | 说明 |
|------|------|------|
| **服务器** | 已有 | 无需额外成本 |
| **API 调用** | 免费 | 开源工具 |
| **AI 分析** | ~¥0.01/视频 | MiMo API |
| **存储** | 免费 | 本地 SQLite |
| **总计** | ~¥0.1/天 | 每天 10 个视频 |

## 📁 项目结构

```
douyin-knowledge-hub/
├── README.md              # 项目说明
├── docs/                  # 文档
│   ├── ARCHITECTURE.md    # 架构设计
│   ├── DEPLOYMENT.md      # 部署指南
│   └── API.md             # API 文档
├── src/                   # 源代码
│   ├── collector/         # 数据采集模块
│   ├── analyzer/          # 内容分析模块
│   ├── storage/           # 知识存储模块
│   └── api/               # API 接口
├── config/                # 配置文件
├── data/                  # 数据目录
├── scripts/               # 脚本工具
├── tests/                 # 测试代码
├── requirements.txt       # Python 依赖
├── Dockerfile             # Docker 配置
└── docker-compose.yml     # Docker 编排
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip
- Git

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/uup557/douyin-knowledge-hub.git
cd douyin-knowledge-hub

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml，填入抖音 Cookie

# 4. 启动服务
python -m src.main
```

## 🔧 配置说明

### 抖音 Cookie 配置

```yaml
douyin:
  cookie: "你的抖音Cookie"
  target_account: "小号抖音ID"
  check_interval: 3600  # 检查间隔（秒）
```

### AI 分析配置

```yaml
ai:
  provider: "mimo"
  api_key: "你的API密钥"
  model: "mimo-v2.5"
```

## 📝 开发日志

### 2026-07-01

- 项目初始化
- 完成架构设计
- 确定技术方案

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目基于 MIT License 开源。

## 📞 联系方式

- GitHub: [@uup557](https://github.com/uup557)
- Email: your-email@example.com

---

**如果这个项目对你有帮助，请给一个 ⭐ Star 支持一下！**
