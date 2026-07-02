"""
知识库查询模块
支持：关键词搜索、语义搜索、对话式问答
"""

import json
import sqlite3
from pathlib import Path

import chromadb
from openai import OpenAI

import os

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "knowledge.db"
CHROMA_PATH = BASE_DIR / "data" / "chroma"

MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_API_BASE = os.getenv("MIMO_API_BASE", "https://api.openai.com/v1")


def get_db():
    """获取数据库连接"""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_chroma():
    """获取 ChromaDB collection"""
    if not CHROMA_PATH.exists():
        return None
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        return client.get_collection("knowledge")
    except Exception:
        return None


# ── 关键词搜索 ──────────────────────────────────────
def search_keyword(query: str, limit: int = 10) -> list[dict]:
    """SQLite关键词搜索"""
    conn = get_db()
    if not conn:
        return []

    try:
        rows = conn.execute(
            """SELECT * FROM videos
            WHERE title LIKE ? OR summary LIKE ? OR keywords LIKE ?
            OR key_points LIKE ? OR transcript LIKE ?
            ORDER BY analyzed_at DESC LIMIT ?""",
            (f"%{query}%",) * 5 + (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── 语义搜索 ──────────────────────────────────────
def search_semantic(query: str, limit: int = 5) -> list[dict]:
    """ChromaDB向量语义搜索"""
    collection = get_chroma()
    if not collection:
        return []

    results = collection.query(query_texts=[query], n_results=limit)

    items = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            items.append({
                "document": doc,
                "metadata": meta,
                "relevance": round(1 - distance, 3),  # cosine similarity
            })

    return items


# ── 对话式问答 ──────────────────────────────────────
def chat_query(question: str) -> str:
    """基于知识库的对话式问答"""
    # 先搜索相关内容
    semantic_results = search_semantic(question, limit=5)
    keyword_results = search_keyword(question, limit=3)

    # 合并搜索结果
    context_parts = []
    seen = set()

    for item in semantic_results:
        doc = item["document"]
        meta = item["metadata"]
        title = meta.get("title", "未知")
        if title not in seen:
            seen.add(title)
            context_parts.append(f"[{title}] {doc[:500]}")

    for item in keyword_results:
        title = item.get("title", "未知")
        if title not in seen:
            seen.add(title)
            context_parts.append(
                f"[{title}] 摘要: {item.get('summary', '')} | "
                f"关键词: {item.get('keywords', '')} | "
                f"要点: {item.get('key_points', '')}"
            )

    if not context_parts:
        return "知识库中没有找到相关内容。"

    context = "\n\n".join(context_parts[:8])

    # 调用AI生成回答
    client = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_API_BASE)

    prompt = f"""你是用户的知识库助手。根据以下知识库中的视频内容，回答用户的问题。

知识库内容：
{context}

用户问题：{question}

请用中文回答，引用具体的视频标题和内容。如果知识库信息不够完整，说明哪些部分是你不确定的。"""

    result = client.chat.completions.create(
        model="mimo-v2.5",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
    )

    return result.choices[0].message.content


# ── 知识库统计 ──────────────────────────────────────
def get_stats() -> dict:
    """获取知识库统计信息"""
    conn = get_db()
    if not conn:
        return {"total": 0, "categories": {}, "difficulty": {}}

    try:
        total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]

        cats = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM videos GROUP BY category ORDER BY cnt DESC"
        ).fetchall()

        diffs = conn.execute(
            "SELECT difficulty, COUNT(*) as cnt FROM videos GROUP BY difficulty ORDER BY cnt DESC"
        ).fetchall()

        return {
            "total": total,
            "categories": {r["category"]: r["cnt"] for r in cats},
            "difficulty": {r["difficulty"]: r["cnt"] for r in diffs},
        }
    finally:
        conn.close()


def list_recent(limit: int = 10) -> list[dict]:
    """列出最近的视频"""
    conn = get_db()
    if not conn:
        return []

    try:
        rows = conn.execute(
            "SELECT aweme_id, title, author, summary, category, difficulty, one_line, analyzed_at "
            "FROM videos ORDER BY analyzed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── CLI ────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法:")
        print("  python query.py search <关键词>      # 关键词搜索")
        print("  python query.py semantic <问题>       # 语义搜索")
        print("  python query.py chat <问题>           # 对话式问答")
        print("  python query.py stats                 # 知识库统计")
        print("  python query.py list                  # 最近收录")
        sys.exit(1)

    action = sys.argv[1]
    query = " ".join(sys.argv[2:])

    if action == "search":
        results = search_keyword(query)
        for r in results:
            print(f"📌 {r['title']} ({r['author']})")
            print(f"   {r['summary']}")
            print()
    elif action == "semantic":
        results = search_semantic(query)
        for r in results:
            print(f"📌 {r['metadata'].get('title', '?')} (相关度: {r['relevance']})")
            print(f"   {r['document'][:200]}...")
            print()
    elif action == "chat":
        answer = chat_query(query)
        print(answer)
    elif action == "stats":
        stats = get_stats()
        print(f"📊 知识库共 {stats['total']} 条记录")
        print(f"   分类: {stats['categories']}")
        print(f"   难度: {stats['difficulty']}")
    elif action == "list":
        items = list_recent()
        for item in items:
            print(f"📌 {item['title']} ({item['author']})")
            print(f"   💡 {item['one_line']}")
            print()
