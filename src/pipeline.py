"""
抖音知识库 - 核心管道
输入：抖音视频链接
输出：AI分析结果 + 存入知识库

流程：链接 → 解析元数据 → 下载视频 → Whisper转录 → MiMo分析 → SQLite + ChromaDB
"""

import asyncio
import json
import os
import sqlite3
import tempfile
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

# API Keys (从环境变量读取)
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", MIMO_API_KEY)  # 默认和MiMo共用
WHISPER_API_BASE = os.getenv("WHISPER_API_BASE", "https://api.openai.com/v1")
MIMO_API_BASE = os.getenv("MIMO_API_BASE", "https://api.openai.com/v1")


# ── Step 1: 解析抖音链接 ─────────────────────────────
async def parse_douyin_link(url: str) -> dict:
    """用 douyin-tiktok-scraper 解析抖音链接，返回视频元数据"""
    from douyin_tiktok_scraper.scraper import Scraper

    api = Scraper()
    result = await api.hybrid_parsing(url)

    # 提取关键信息
    if "data" in result:
        data = result["data"]
        return {
            "aweme_id": data.get("aweme_id", ""),
            "title": data.get("desc", "无标题"),
            "author": data.get("author", {}).get("nickname", "未知"),
            "author_id": data.get("author", {}).get("unique_id", ""),
            "duration": data.get("duration", 0),
            "create_time": data.get("create_time", 0),
            "likes": data.get("statistics", {}).get("digg_count", 0),
            "comments": data.get("statistics", {}).get("comment_count", 0),
            "shares": data.get("statistics", {}).get("share_count", 0),
            "video_url": (
                data.get("video", {}).get("play_addr", {}).get("url_list", [None])[0]
                or data.get("video", {}).get("play_addr_h264", {}).get("url_list", [None])[0]
            ),
            "cover": data.get("video", {}).get("cover", {}).get("url_list", [None])[0],
            "tags": [t.get("title", "") for t in data.get("text_extra", []) if t.get("title")],
            "raw": data,
        }

    return {"error": f"解析失败: {result}"}


# ── Step 2: 下载视频（临时） ──────────────────────────
async def download_video(video_url: str, aweme_id: str) -> Path | None:
    """下载视频到临时目录，返回文件路径"""
    if not video_url:
        return None

    video_path = TEMP_DIR / f"{aweme_id}.mp4"
    if video_path.exists():
        return video_path

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(video_url, follow_redirects=True)
        if resp.status_code == 200:
            video_path.write_bytes(resp.content)
            return video_path

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
    """用 MiMo 分析内容，生成摘要、关键词、学习要点"""

    client = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_API_BASE)

    prompt = f"""你是一个知识整理助手。请分析以下抖音视频内容，返回JSON格式的分析结果。

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
  "one_line": "一句话总结这个视频的核心价值"
}}"""

    result = client.chat.completions.create(
        model="mimo-v2.5",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
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
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aweme_id TEXT UNIQUE,
            title TEXT,
            author TEXT,
            author_id TEXT,
            duration INTEGER,
            create_time INTEGER,
            likes INTEGER,
            comments INTEGER,
            shares INTEGER,
            tags TEXT,
            transcript TEXT,
            summary TEXT,
            keywords TEXT,
            key_points TEXT,
            difficulty TEXT,
            category TEXT,
            learning_value TEXT,
            one_line TEXT,
            url TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def init_chroma():
    """初始化 ChromaDB 向量库"""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(
        name="knowledge",
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def save_to_db(metadata: dict, analysis: dict, transcript: str, url: str):
    """保存到 SQLite"""
    conn = init_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO videos
            (aweme_id, title, author, author_id, duration, create_time,
             likes, comments, shares, tags, transcript,
             summary, keywords, key_points, difficulty, category,
             learning_value, one_line, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metadata.get("aweme_id", ""),
                metadata.get("title", ""),
                metadata.get("author", ""),
                metadata.get("author_id", ""),
                metadata.get("duration", 0),
                metadata.get("create_time", 0),
                metadata.get("likes", 0),
                metadata.get("comments", 0),
                metadata.get("shares", 0),
                json.dumps(metadata.get("tags", []), ensure_ascii=False),
                transcript,
                analysis.get("summary", ""),
                json.dumps(analysis.get("keywords", []), ensure_ascii=False),
                json.dumps(analysis.get("key_points", []), ensure_ascii=False),
                analysis.get("difficulty", ""),
                analysis.get("category", ""),
                analysis.get("learning_value", ""),
                analysis.get("one_line", ""),
                url,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_to_chroma(metadata: dict, analysis: dict, transcript: str):
    """保存到 ChromaDB 向量库"""
    collection = init_chroma()

    # 组合文本用于embedding
    doc_text = f"""
标题：{metadata.get('title', '')}
作者：{metadata.get('author', '')}
摘要：{analysis.get('summary', '')}
关键词：{', '.join(analysis.get('keywords', []))}
学习要点：{'; '.join(analysis.get('key_points', []))}
分类：{analysis.get('category', '')}
难度：{analysis.get('difficulty', '')}
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
        }],
    )


def cleanup_temp(video_path: Path | None):
    """清理临时视频文件"""
    if video_path and video_path.exists():
        video_path.unlink()


# ── 主流程 ──────────────────────────────────────────
async def process_video(url: str) -> dict:
    """
    完整管道：输入抖音链接 → 输出分析结果
    """
    print(f"[1/5] 解析链接: {url}")
    metadata = await parse_douyin_link(url)
    if "error" in metadata:
        return {"success": False, "error": metadata["error"]}

    aweme_id = metadata.get("aweme_id", "")
    title = metadata.get("title", "")
    print(f"  → {title} (by {metadata.get('author', '?')})")

    print(f"[2/5] 下载视频...")
    video_path = await download_video(metadata.get("video_url", ""), aweme_id)
    video_size = video_path.stat().st_size if video_path else 0
    print(f"  → 下载完成: {video_size / 1024 / 1024:.1f}MB")

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
        analysis = analyze_content(title, transcript, metadata.get("tags", []), metadata.get("author", ""))
        print(f"  → 分析完成: {analysis.get('one_line', '')}")
    except Exception as e:
        print(f"  → 分析失败: {e}")
        analysis = {
            "summary": "分析失败",
            "keywords": [],
            "key_points": [],
            "difficulty": "未知",
            "category": "其他",
            "learning_value": "未知",
            "one_line": "AI分析失败",
        }

    print(f"[5/5] 存入知识库...")
    save_to_db(metadata, analysis, transcript, url)
    save_to_chroma(metadata, analysis, transcript)
    cleanup_temp(video_path)
    print(f"  → 存储完成 ✓")

    return {
        "success": True,
        "aweme_id": aweme_id,
        "title": title,
        "author": metadata.get("author", ""),
        "summary": analysis.get("summary", ""),
        "keywords": analysis.get("keywords", []),
        "key_points": analysis.get("key_points", []),
        "difficulty": analysis.get("difficulty", ""),
        "category": analysis.get("category", ""),
        "learning_value": analysis.get("learning_value", ""),
        "one_line": analysis.get("one_line", ""),
        "transcript": transcript[:500] if transcript else "",
        "tags": metadata.get("tags", []),
    }


# ── CLI 入口 ────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python pipeline.py <抖音链接>")
        sys.exit(1)

    url = sys.argv[1]
    result = asyncio.run(process_video(url))

    print("\n" + "=" * 50)
    if result.get("success"):
        print(f"✅ {result['title']}")
        print(f"👤 {result['author']}")
        print(f"📝 {result['summary']}")
        print(f"🔑 关键词: {', '.join(result['keywords'])}")
        print(f"📊 难度: {result['difficulty']} | 分类: {result['category']}")
        print(f"💡 {result['one_line']}")
    else:
        print(f"❌ {result.get('error', '未知错误')}")
