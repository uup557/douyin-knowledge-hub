"""
抖音知识库 v2 - 基于页面解析的完整管道
不需要任何API Key就能解析抖音链接！

流程：分享链接 → 解析页面HTML → 下载视频 → Whisper转录 → MiMo分析 → 知识库
"""

import asyncio
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import chromadb
import httpx
from openai import OpenAI


# ── 配置 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "knowledge.db"
CHROMA_PATH = DATA_DIR / "chroma"
TEMP_DIR = DATA_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

MIMO_API_KEY=os.getenv("MIMO_API_KEY", "")
MIMO_API_BASE = os.getenv("MIMO_API_BASE", "https://api.openai.com/v1")
WHISPER_API_KEY=os.getenv("WHISPER_API_KEY", MIMO_API_KEY)
WHISPER_API_BASE = os.getenv("WHISPER_API_BASE", "https://api.openai.com/v1")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ── Step 1: 解析抖音链接 ─────────────────────────────
async def parse_douyin_link(url: str) -> dict:
    """从抖音分享页面HTML提取视频元数据和下载URL"""

    # 先解析短链接，获取真实URL
    real_url = url
    if "v.douyin.com" in url or "vm.tiktok.com" in url:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            real_url = str(resp.url)

    # 从URL提取视频ID
    vid_match = re.search(r"video/(\d+)", real_url)
    aweme_id = vid_match.group(1) if vid_match else ""

    # 获取页面HTML
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(real_url, headers=HEADERS)
        html = resp.text

    # 提取标题（从 og:description 或页面描述）
    title = ""
    author = ""
    likes = 0
    video_url = ""

    # 方法1：从描述提取（格式："标题 - 作者于日期发布在抖音，已经收获了N个喜欢"）
    desc_match = re.search(
        r'content="([^"]*?)(?:\s*-\s*)([^\s]+)于(\d{8})发布在抖音，已经收获了(\d+)个喜欢',
        html,
    )
    if desc_match:
        title = desc_match.group(1).strip()
        author = desc_match.group(2).strip()
        likes = int(desc_match.group(4))

    # 方法2：从页面JSON数据提取
    if not title:
        title_match = re.search(r'"desc"\s*:\s*"([^"]{2,})"', html)
        if title_match:
            title = title_match.group(1)

    if not author:
        author_match = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
        if author_match:
            author = author_match.group(1)

    # 提取视频下载URL
    play_match = re.search(
        r'"play_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\["([^"]+)"', html
    )
    if play_match:
        video_url = play_match.group(1).replace("\\u002F", "/")

    # 提取标签
    tags = re.findall(r'"title"\s*:\s*"([^"]+)"', html)
    tags = [t for t in tags if t not in (title, author) and len(t) < 20][:5]

    return {
        "aweme_id": aweme_id,
        "title": title or "未知标题",
        "author": author or "未知作者",
        "likes": likes,
        "video_url": video_url,
        "tags": tags,
        "url": url,
        "real_url": real_url,
    }


# ── Step 2: 下载视频（临时） ──────────────────────────
async def download_video(video_url: str, aweme_id: str) -> Path | None:
    """下载视频到临时目录"""
    if not video_url:
        return None

    video_path = TEMP_DIR / f"{aweme_id}.mp4"
    if video_path.exists():
        return video_path

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(
                video_url,
                headers={
                    **HEADERS,
                    "Referer": "https://www.douyin.com/",
                },
            )
            if resp.status_code == 200 and len(resp.content) > 10000:
                video_path.write_bytes(resp.content)
                return video_path
    except Exception as e:
        print(f"  下载失败: {e}")

    return None


# ── Step 3: Whisper 转录 ──────────────────────────────
def transcribe_audio(video_path: Path) -> str:
    """用 OpenAI Whisper API 转录音频"""
    if not video_path or not video_path.exists():
        return ""

    client = OpenAI(api_key=WHISPER_API_KEY, base_url=WHISPER_API_BASE)

    with open(video_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="zh",
            response_format="text",
        )

    return result


# ── Step 4: MiMo AI 分析 ─────────────────────────────
def analyze_content(title: str, transcript: str, tags: list, author: str) -> dict:
    """用 MiMo 分析内容，包含知识分层标签"""

    client = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_API_BASE)

    prompt = f"""你是一个知识整理助手。请分析以下视频内容，返回JSON格式的分析结果。

视频标题：{title}
视频作者：{author}
相关标签：{', '.join(tags) if tags else '无'}
视频转录文字：
{transcript[:3000] if transcript else '（无转录文字）'}

请返回以下JSON格式（不要添加任何其他文字）：
{{
  "summary": "100字以内的内容摘要",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "key_points": ["学习要点1", "学习要点2", "学习要点3"],
  "difficulty": "初级/中级/高级",
  "category": "分类（如：技术/生活/教育/其他）",
  "learning_value": "高/中/低",
  "one_line": "一句话总结这个视频的核心价值",
  "content_type": "教程/工具/框架/观点/新闻/案例",
  "tech_domain": ["AI", "前端", "后端", "DevOps", "数据", "安全", "其他"],
  "importance": "核心/参考/趋势",
  "maturity": "生产就绪/实验阶段/已废弃"
}}"""

    result = client.chat.completions.create(
        model="mimo-v2.5",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
    )

    content = result.choices[0].message.content.strip()

    # 提取JSON
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    return json.loads(content)


# ── Step 5: 存储 ─────────────────────────────────────
def init_db():
    """初始化 SQLite"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aweme_id TEXT UNIQUE,
            title TEXT,
            author TEXT,
            tags TEXT,
            transcript TEXT,
            summary TEXT,
            keywords TEXT,
            key_points TEXT,
            difficulty TEXT,
            category TEXT,
            learning_value TEXT,
            one_line TEXT,
            likes INTEGER,
            url TEXT,
            content_type TEXT,
            tech_domain TEXT,
            importance TEXT,
            maturity TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def init_chroma():
    """初始化 ChromaDB"""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(
        name="knowledge",
        metadata={"hnsw:space": "cosine"},
    )


def save_to_db(metadata: dict, analysis: dict, transcript: str):
    """保存到 SQLite"""
    conn = init_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO videos
            (aweme_id, title, author, tags, transcript, summary, keywords,
             key_points, difficulty, category, learning_value, one_line, likes, url,
             content_type, tech_domain, importance, maturity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metadata.get("aweme_id", ""),
                metadata.get("title", ""),
                metadata.get("author", ""),
                json.dumps(metadata.get("tags", []), ensure_ascii=False),
                transcript,
                analysis.get("summary", ""),
                json.dumps(analysis.get("keywords", []), ensure_ascii=False),
                json.dumps(analysis.get("key_points", []), ensure_ascii=False),
                analysis.get("difficulty", ""),
                analysis.get("category", ""),
                analysis.get("learning_value", ""),
                analysis.get("one_line", ""),
                metadata.get("likes", 0),
                metadata.get("url", ""),
                analysis.get("content_type", ""),
                json.dumps(analysis.get("tech_domain", []), ensure_ascii=False),
                analysis.get("importance", ""),
                analysis.get("maturity", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_to_chroma(metadata: dict, analysis: dict, transcript: str):
    """保存到 ChromaDB 向量库"""
    collection = init_chroma()

    doc_text = f"""
标题：{metadata.get('title', '')}
作者：{metadata.get('author', '')}
摘要：{analysis.get('summary', '')}
关键词：{', '.join(analysis.get('keywords', []))}
学习要点：{'; '.join(analysis.get('key_points', []))}
分类：{analysis.get('category', '')}
难度：{analysis.get('difficulty', '')}
内容类型：{analysis.get('content_type', '')}
技术领域：{', '.join(analysis.get('tech_domain', []))}
重要程度：{analysis.get('importance', '')}
转录：{transcript[:1500] if transcript else ''}
"""

    collection.upsert(
        ids=[metadata.get("aweme_id", str(time.time()))],
        documents=[doc_text.strip()],
        metadatas=[{
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "category": analysis.get("category", ""),
            "difficulty": analysis.get("difficulty", ""),
            "keywords": ", ".join(analysis.get("keywords", [])),
            "content_type": analysis.get("content_type", ""),
            "tech_domain": ", ".join(analysis.get("tech_domain", [])),
            "importance": analysis.get("importance", ""),
            "maturity": analysis.get("maturity", ""),
        }],
    )


def cleanup_temp(video_path: Path | None):
    """清理临时文件"""
    if video_path and video_path.exists():
        video_path.unlink()


# ── 主流程 ──────────────────────────────────────────
async def process_video(url: str) -> dict:
    """完整管道：输入抖音链接 → 输出分析结果"""

    print(f"[1/5] 解析链接: {url}")
    metadata = await parse_douyin_link(url)
    if not metadata.get("title") or metadata["title"] == "未知标题":
        return {"success": False, "error": "无法解析视频信息，请检查链接是否有效"}

    aweme_id = metadata.get("aweme_id", "")
    title = metadata.get("title", "")
    author = metadata.get("author", "")
    print(f"  → 「{title}」 by {author}")

    print(f"[2/5] 下载视频...")
    video_path = await download_video(metadata.get("video_url", ""), aweme_id)
    if video_path:
        size_mb = video_path.stat().st_size / 1024 / 1024
        print(f"  → 下载完成: {size_mb:.1f}MB")
    else:
        print(f"  → 视频下载失败，仅分析元数据")

    print(f"[3/5] Whisper 转录...")
    transcript = ""
    if video_path:
        try:
            transcript = transcribe_audio(video_path)
            print(f"  → 转录完成: {len(transcript)}字")
        except Exception as e:
            print(f"  → 转录失败: {e}")

    print(f"[4/5] MiMo 分析...")
    analysis = {}
    try:
        analysis = analyze_content(title, transcript, metadata.get("tags", []), author)
        print(f"  → {analysis.get('one_line', '分析完成')}")
        print(f"  → 内容类型: {analysis.get('content_type', '')} | 重要程度: {analysis.get('importance', '')}")
    except Exception as e:
        print(f"  → 分析失败: {e}")
        analysis = {
            "summary": f"视频「{title}」by {author}",
            "keywords": metadata.get("tags", []),
            "key_points": [],
            "difficulty": "未知",
            "category": "其他",
            "learning_value": "未知",
            "one_line": title,
            "content_type": "其他",
            "tech_domain": ["其他"],
            "importance": "参考",
            "maturity": "未知",
        }

    print(f"[5/5] 存入知识库...")
    save_to_db(metadata, analysis, transcript)
    save_to_chroma(metadata, analysis, transcript)
    cleanup_temp(video_path)
    print(f"  → ✓ 已存入知识库")

    return {
        "success": True,
        "aweme_id": aweme_id,
        "title": title,
        "author": author,
        "summary": analysis.get("summary", ""),
        "keywords": analysis.get("keywords", []),
        "key_points": analysis.get("key_points", []),
        "difficulty": analysis.get("difficulty", ""),
        "category": analysis.get("category", ""),
        "learning_value": analysis.get("learning_value", ""),
        "one_line": analysis.get("one_line", ""),
        "content_type": analysis.get("content_type", ""),
        "tech_domain": analysis.get("tech_domain", []),
        "importance": analysis.get("importance", ""),
        "maturity": analysis.get("maturity", ""),
        "transcript_preview": transcript[:300] if transcript else "",
        "tags": metadata.get("tags", []),
        "likes": metadata.get("likes", 0),
    }


# ── CLI ────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python pipeline_v2.py <抖音链接>")
        sys.exit(1)

    url = sys.argv[1]
    result = asyncio.run(process_video(url))

    print("\n" + "=" * 50)
    if result.get("success"):
        print(f"✅ {result['title']}")
        print(f"👤 {result['author']} | ❤️ {result['likes']}")
        print(f"📝 {result['summary']}")
        print(f"🔑 关键词: {', '.join(result['keywords'])}")
        print(f"📊 难度: {result['difficulty']} | 分类: {result['category']}")
        print(f"🏷️ 内容类型: {result['content_type']} | 重要程度: {result['importance']}")
        print(f"💻 技术领域: {', '.join(result['tech_domain'])}")
        print(f"💡 {result['one_line']}")
    else:
        print(f"❌ {result.get('error', '未知错误')}")
