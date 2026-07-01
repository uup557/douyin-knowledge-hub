# 架构设计文档

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层 (Future)                        │
│              Web UI / CLI / 飞书机器人                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    API 接口层                                 │
│              FastAPI RESTful API                             │
│  ┌─────────┬─────────┬─────────┬─────────┐                 │
│  │ 视频查询 │ 知识搜索 │ 学习报告 │ 系统管理 │                 │
│  └─────────┴─────────┴─────────┴─────────┘                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    业务逻辑层                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 视频监控服务                          │   │
│  │  • 定时轮询小号分享视频                               │   │
│  │  • 检测新视频                                         │   │
│  │  • 触发内容分析                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 内容分析服务                          │   │
│  │  • AI 内容理解                                        │   │
│  │  • 关键词提取                                         │   │
│  │  • 摘要生成                                           │   │
│  │  • 标签分类                                           │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 知识库服务                            │   │
│  │  • 数据存储                                           │   │
│  │  • 全文搜索                                           │   │
│  │  • 知识图谱                                           │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    数据层                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   SQLite    │  │  文件存储    │  │  缓存存储    │        │
│  │  知识库     │  │  视频元数据  │  │  会话缓存    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    外部服务层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  抖音 API   │  │  MiMo API   │  │  Whisper    │        │
│  │  视频采集   │  │  内容分析    │  │  语音转文字  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块

#### 1. 视频监控模块 (Video Monitor)

**职责**：
- 定时检查抖音小号的分享视频
- 检测新视频并记录
- 触发内容分析流程

**实现**：
```python
class VideoMonitor:
    def __init__(self, config):
        self.config = config
        self.douyin_api = DouyinAPI(config.cookie)
        self.db = Database(config.db_path)
    
    async def check_new_videos(self):
        """检查新视频"""
        videos = await self.douyin_api.get_user_videos(
            self.config.target_account
        )
        
        for video in videos:
            if not self.db.video_exists(video.id):
                await self.process_new_video(video)
    
    async def process_new_video(self, video):
        """处理新视频"""
        # 1. 保存元数据
        self.db.save_video(video)
        
        # 2. 触发内容分析
        await self.analyzer.analyze(video)
        
        # 3. 保存分析结果
        self.db.save_analysis(video.id, analysis)
```

#### 2. 内容分析模块 (Content Analyzer)

**职责**：
- 分析视频标题和描述
- 提取技术关键词
- 生成内容摘要
- （可选）语音转文字

**实现**：
```python
class ContentAnalyzer:
    def __init__(self, config):
        self.ai_client = MiMoClient(config.api_key)
    
    async def analyze(self, video):
        """分析视频内容"""
        # 构建分析提示
        prompt = f"""
        分析以下技术视频：
        标题：{video.title}
        描述：{video.description}
        标签：{video.tags}
        
        请提供：
        1. 内容摘要（100字以内）
        2. 技术关键词（3-5个）
        3. 学习要点（3-5条）
        4. 难度等级（初级/中级/高级）
        5. 推荐标签
        """
        
        # 调用 AI 分析
        result = await self.ai_client.analyze(prompt)
        
        return AnalysisResult(
            summary=result.summary,
            keywords=result.keywords,
            key_points=result.key_points,
            difficulty=result.difficulty,
            tags=result.tags
        )
```

#### 3. 知识库模块 (Knowledge Base)

**职责**：
- 存储视频元数据和分析结果
- 支持全文搜索
- 支持标签分类
- （可选）知识图谱

**实现**：
```python
class KnowledgeBase:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.init_tables()
    
    def init_tables(self):
        """初始化数据库表"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                tags TEXT,
                created_at TIMESTAMP,
                analyzed_at TIMESTAMP
            )
        """)
        
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                video_id TEXT PRIMARY KEY,
                summary TEXT,
                keywords TEXT,
                key_points TEXT,
                difficulty TEXT,
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        """)
    
    def search(self, query):
        """全文搜索"""
        return self.db.execute("""
            SELECT v.*, a.summary, a.keywords
            FROM videos v
            LEFT JOIN analyses a ON v.id = a.video_id
            WHERE v.title LIKE ? OR v.description LIKE ?
            OR a.summary LIKE ? OR a.keywords LIKE ?
        """, (f"%{query}%",) * 4).fetchall()
```

### 数据流

```
┌─────────────┐
│  抖音小号   │
└──────┬──────┘
       │ 分享视频
       ▼
┌─────────────┐
│  视频监控   │ ← 定时轮询（每小时）
└──────┬──────┘
       │ 新视频
       ▼
┌─────────────┐
│  元数据提取 │
└──────┬──────┘
       │ 视频信息
       ▼
┌─────────────┐
│  内容分析   │ ← AI 分析
└──────┬──────┘
       │ 分析结果
       ▼
┌─────────────┐
│  知识库存储 │
└──────┬──────┘
       │ 查询
       ▼
┌─────────────┐
│  用户查询   │ → 返回结果
└─────────────┘
```

### 安全设计

1. **Cookie 安全**：
   - 加密存储
   - 定期刷新
   - 不上传到 GitHub

2. **API 安全**：
   - API Key 环境变量
   - 请求频率限制
   - 错误处理

3. **数据安全**：
   - 本地存储
   - 定期备份
   - 敏感信息脱敏

### 性能优化

1. **并发处理**：
   - 异步 I/O
   - 并发分析多个视频

2. **缓存策略**：
   - 已分析视频缓存
   - 搜索结果缓存

3. **资源控制**：
   - 请求频率限制
   - 内存使用监控

### 扩展性设计

1. **插件架构**：
   - 可替换 AI 提供商
   - 可扩展数据源
   - 可添加新分析维度

2. **API 设计**：
   - RESTful 接口
   - 版本管理
   - 文档自动生成

3. **部署方式**：
   - 本地运行
   - Docker 部署
   - 云服务部署
