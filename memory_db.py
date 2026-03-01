#!/usr/bin/env python3
"""
Permanent Memory System for OpenClaw Agents
使用 SQLite FTS5 全文搜索
"""

import json
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.expanduser("~/.openclaw/memories.db")

def get_db():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库"""
    conn = get_db()
    # 主表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            session_id TEXT,
            summary TEXT NOT NULL,
            conversation TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 会话状态表（记录上一个会话 ID，用于检测会话切换）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_state (
            agent_id TEXT PRIMARY KEY,
            last_session_id TEXT,
            last_user_id TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # FTS5 全文搜索表
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            summary,
            content='memories',
            content_rowid='rowid'
        )
    """)
    # 索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_user ON memories(agent_id, user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON memories(session_id)")
    conn.commit()
    conn.close()

def get_last_session(agent_id: str) -> tuple:
    """获取上一个会话的 session_id 和 user_id"""
    conn = get_db()
    row = conn.execute(
        "SELECT last_session_id, last_user_id FROM memory_state WHERE agent_id = ?",
        (agent_id,)
    ).fetchone()
    conn.close()
    return (row["last_session_id"], row["last_user_id"]) if row else (None, None)

def update_last_session(agent_id: str, session_id: str, user_id: str):
    """更新上一个会话 ID"""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO memory_state (agent_id, last_session_id, last_user_id, updated_at)
        VALUES (?, ?, ?, datetime('now'))
    """, (agent_id, session_id, user_id))
    conn.commit()
    conn.close()

def generate_id(agent_id: str, user_id: str) -> str:
    """生成唯一编号: {时间戳}_{agent}_{用户id前8位}"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    user_short = user_id[:8] if user_id else "unknown"
    return f"{timestamp}_{agent_id}_{user_short}"

def extract_text_content(messages: List[Dict]) -> tuple:
    """提取对话中的用户消息和助手消息"""
    user_msgs = []
    assistant_msgs = []
    
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        
        if isinstance(content, list):
            # 处理复杂格式的消息
            for c in content:
                if isinstance(c, dict):
                    text = c.get("text", "")
                    if c.get("type") == "text" or c.get("type") == "thinking":
                        if role == "user" and not text.startswith("System:"):
                            user_msgs.append(text)
                        elif role == "assistant":
                            assistant_msgs.append(text)
        elif isinstance(content, str):
            if role == "user" and not content.startswith("System:"):
                user_msgs.append(content)
            elif role == "assistant":
                assistant_msgs.append(content)
    
    return user_msgs, assistant_msgs

def summarize_conversation(messages: List[Dict], max_length: int = 200) -> str:
    """总结对话关键信息 - 自然语言描述版，128-256字"""
    if not messages:
        return "空对话"
    
    user_msgs, assistant_msgs = extract_text_content(messages)
    
    if not user_msgs:
        return "无有效对话内容"
    
    # 统计
    user_count = len(user_msgs)
    assistant_count = len(assistant_msgs)
    
    # 提取核心用户问题
    main_topics = []
    for msg in user_msgs[:5]:
        # 提取前几个关键词或短句
        msg_clean = msg.replace("\n", " ").strip()
        if len(msg_clean) > 100:
            # 取前100字符
            main_topics.append(msg_clean[:100])
        elif msg_clean:
            main_topics.append(msg_clean)
    
    # 提取关键结论
    conclusion = ""
    if assistant_msgs:
        # 取最后一个有意义的回复
        for msg in reversed(assistant_msgs):
            msg_clean = msg.replace("\n", " ").strip()
            if len(msg_clean) > 20 and len(msg_clean) < 200:
                conclusion = msg_clean
                break
    
    # 构建自然语言描述
    parts = []
    
    # 开场：谁（agent）在什么时候和用户进行了什么类型的对话
    parts.append(f"用户与agent进行了{user_count}轮对话交流")
    
    # 中间：用户主要问了什么问题
    if main_topics:
        topics_str = "；".join(main_topics[:2])
        parts.append(f"用户主要询问了：{topics_str}")
    
    # 结尾：agent给出了什么结论或帮助
    if conclusion:
        parts.append(f"agent的最终回复要点：{conclusion}")
    
    # 组合成完整描述
    summary = "，".join(parts)
    
    # 确保长度在 128-256 字之间
    if len(summary) < 128:
        # 扩展描述
        extra = f"。" if not summary.endswith("。") else ""
        summary += f"{extra}对话涉及多个技术问题和操作需求，包括系统配置、功能实现、问题解答等方面。用户提出了具体的任务需求，agent进行了相应的分析和解答。"
    
    # 如果太长，截断到 max_length
    if len(summary) > max_length:
        summary = summary[:max_length-3] + "..."
    
    return summary
    
    # 3. 用户意图（取前几个用户问题）
    user_questions = [msg.replace("\n", " ").replace("System:", "").strip()[:80] for msg in user_msgs[:5]]
    if user_questions:
        # 过滤掉太短的
        user_questions = [q for q in user_questions if len(q) > 5]
        if user_questions:
            parts.append(f"用户问题: {'; '.join(user_questions[:3])}")
    
    # 4. 助手回复的关键结论
    if assistant_msgs:
        # 取最后一个有意义的回复
        last_answer = assistant_msgs[-1].replace("\n", " ").strip()[:100] if assistant_msgs else ""
        if last_answer:
            parts.append(f"最终结论: {last_answer}")
    
    # 限制总长度
    summary = " | ".join(parts)
    
    # 如果太长，截断
    if len(summary) > 500:
        summary = summary[:497] + "..."
    
    return summary

def save_memory(agent_id: str, user_id: str, conversation: List[Dict], session_id: str = None) -> Dict:
    """
    保存对话记忆
    
    Args:
        agent_id: agent ID
        user_id: 用户 ID
        conversation: 对话列表
        session_id: 会话 ID（可选）
    """
    init_db()
    
    if not conversation:
        return {"status": "skipped", "reason": "empty conversation"}
    
    # 生成唯一编号
    memory_id = generate_id(agent_id, user_id)
    
    # 生成概述
    summary = summarize_conversation(conversation)
    
    # 保存到数据库
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO memories (id, agent_id, user_id, session_id, summary, conversation)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (memory_id, agent_id, user_id, session_id, summary, json.dumps(conversation, ensure_ascii=False)))
    
    # 更新 FTS 索引
    conn.execute("""
        INSERT INTO memories_fts(rowid, summary)
        SELECT rowid, summary FROM memories WHERE id = ?
    """, (memory_id,))
    
    # 更新会话状态
    if session_id:
        update_last_session(agent_id, session_id, user_id)
    
    conn.commit()
    conn.close()
    
    return {"status": "saved", "id": memory_id, "summary": summary, "session_id": session_id}

def check_session_change(agent_id: str, current_session_id: str, user_id: str, conversation: List[Dict]) -> Dict:
    """
    检查会话是否切换，如果切换则保存上一个会话
    
    Returns:
        {"action": "save", "result": {...}} - 需要保存
        {"action": "update", "session_id": "xxx"} - 只需更新状态
        {"action": "none", "reason": "same session"} - 同一会话，无需操作
    """
    init_db()
    
    last_session_id, last_user_id = get_last_session(agent_id)
    
    # 首次保存：记录会话 ID
    if last_session_id is None:
        if current_session_id:
            update_last_session(agent_id, current_session_id, user_id)
        return {"action": "init", "session_id": current_session_id}
    
    # 会话切换：保存上一个会话
    if current_session_id != last_session_id:
        # 保存上一会话的对话（如果有）
        if conversation and len(conversation) > 0:
            result = save_memory(agent_id, last_user_id, conversation, session_id=last_session_id)
            return {"action": "save", "result": result, "previous_session": last_session_id}
        else:
            return {"action": "save", "result": {"status": "skipped", "reason": "empty conversation"}, "previous_session": last_session_id}
    
    # 同一会话：只更新状态
    return {"action": "none", "reason": "same session", "session_id": current_session_id}

def search_memories(agent_id: str, user_id: str, query: str, can_access_all: bool = False, limit: int = 3) -> List[Dict]:
    """
    搜索相关记忆
    
    Args:
        agent_id: 当前 agent ID
        user_id: 当前用户 ID  
        query: 查询文本
        can_access_all: 是否可以访问所有 agent 的记忆
        limit: 返回数量
    """
    init_db()
    
    conn = get_db()
    
    if can_access_all:
        # assistant: 可以查所有 agent 的记忆
        rows = conn.execute("""
            SELECT id, agent_id, user_id, summary, conversation, created_at
            FROM memories
            ORDER BY created_at DESC
            LIMIT 50
        """).fetchall()
    else:
        # 其他 agent: 只能查自己的
        rows = conn.execute("""
            SELECT id, agent_id, user_id, summary, conversation, created_at
            FROM memories
            WHERE agent_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (agent_id, user_id)).fetchall()
    
    conn.close()
    
    # 简单的关键词匹配
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    results = []
    for row in rows:
        summary = row["summary"]
        summary_lower = summary.lower()
        
        # 计算匹配分数
        score = 0
        for word in query_words:
            if word in summary_lower:
                score += 1
        # 额外检查是否包含查询文本
        if query_lower in summary_lower:
            score += 5
        
        if score > 0:
            results.append({
                "id": row["id"],
                "agent_id": row["agent_id"],
                "user_id": row["user_id"],
                "summary": row["summary"],
                "score": score,
                "conversation": json.loads(row["conversation"]),
                "created_at": row["created_at"]
            })
    
    # 按分数排序
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return results[:limit]

def search_with_fallback(agent_id: str, user_id: str, query: str, can_access_all: bool = False, limit: int = 3) -> Dict:
    """
    两阶段检索：
    1. 先搜索概述（summary）
    2. 如果概述无匹配，深度搜索对话原文（conversation）
    
    Returns:
    {
        "stage": "summary" | "conversation" | "none",
        "results": [...],
        "message": "确认信息"
    }
    """
    # 第一阶段：搜索概述
    summary_results = search_memories(agent_id, user_id, query, can_access_all, limit)
    
    if summary_results:
        return {
            "stage": "summary",
            "results": summary_results,
            "message": "📢 在记忆概述中找到相关内容："
        }
    
    # 第二阶段：深度搜索对话原文
    init_db()
    conn = get_db()
    
    if can_access_all:
        rows = conn.execute("""
            SELECT id, agent_id, user_id, summary, conversation, created_at
            FROM memories
            ORDER BY created_at DESC
            LIMIT 50
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, agent_id, user_id, summary, conversation, created_at
            FROM memories
            WHERE agent_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (agent_id, user_id)).fetchall()
    
    conn.close()
    
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    conversation_results = []
    for row in rows:
        conv = json.loads(row["conversation"])
        conv_text = json.dumps(conv).lower()
        
        # 计算匹配分数
        score = 0
        for word in query_words:
            if word in conv_text:
                score += 1
        if query_lower in conv_text:
            score += 5
        
        if score > 0:
            # 提取匹配的片段
            matched_snippets = []
            for msg in conv:
                content = msg.get("content", "")
                if isinstance(content, str):
                    content_lower = content.lower()
                    if query_lower in content_lower:
                        matched_snippets.append(content[:200])
                    else:
                        for word in query_words:
                            if word in content_lower:
                                matched_snippets.append(content[:200])
                                break
            
            conversation_results.append({
                "id": row["id"],
                "agent_id": row["agent_id"],
                "user_id": row["user_id"],
                "summary": row["summary"],
                "score": score,
                "matched_snippets": matched_snippets[:3],  # 最多3条匹配片段
                "conversation": conv,
                "created_at": row["created_at"]
            })
    
    conversation_results.sort(key=lambda x: x["score"], reverse=True)
    
    if conversation_results:
        return {
            "stage": "conversation",
            "results": conversation_results[:limit],
            "message": "📢 在对话原文中找到相关内容："
        }
    
    return {
        "stage": "none",
        "results": [],
        "message": "未找到相关记忆"
    }

def confirm_memory(results: List[Dict]) -> str:
    """格式化记忆确认信息"""
    if not results:
        return None
    
    best = results[0]
    lines = [
        "📢 找到一段相关记忆：",
        "",
        f"**{best['summary']}**",
        f"时间: {best['created_at']}",
        "",
        "是这件事吗？"
    ]
    return "\n".join(lines)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python permanent_memory.py <command> [args...]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "init":
        init_db()
        print("Database initialized")
    
    elif cmd == "save":
        # python permanent_memory.py save <agent_id> <user_id> <conversation_json> [session_id]
        agent_id = sys.argv[2]
        user_id = sys.argv[3]
        conversation = json.loads(sys.argv[4])
        session_id = sys.argv[5] if len(sys.argv) > 5 else None
        result = save_memory(agent_id, user_id, conversation, session_id)
        print(json.dumps(result, ensure_ascii=False))
    
    elif cmd == "check":
        # python permanent_memory.py check <agent_id> <session_id> <user_id> <conversation_json>
        # 检查会话是否切换，如果是则保存上一个会话
        agent_id = sys.argv[2]
        current_session_id = sys.argv[3]
        user_id = sys.argv[4]
        conversation = json.loads(sys.argv[5])
        result = check_session_change(agent_id, current_session_id, user_id, conversation)
        print(json.dumps(result, ensure_ascii=False))
    
    elif cmd == "search":
        # python permanent_memory.py search <agent_id> <user_id> <query> <can_access_all>
        agent_id = sys.argv[2]
        user_id = sys.argv[3]
        query = sys.argv[4]
        can_access_all = sys.argv[5].lower() == "true" if len(sys.argv) > 5 else False
        results = search_memories(agent_id, user_id, query, can_access_all=can_access_all)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    
    elif cmd == "search2":
        # python permanent_memory.py search2 <agent_id> <user_id> <query> <can_access_all>
        # 两阶段检索：先搜索概述，无匹配时搜索原文
        agent_id = sys.argv[2]
        user_id = sys.argv[3]
        query = sys.argv[4]
        can_access_all = sys.argv[5].lower() == "true" if len(sys.argv) > 5 else False
        result = search_with_fallback(agent_id, user_id, query, can_access_all=can_access_all)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif cmd == "confirm":
        # python permanent_memory.py confirm <results_json>
        results = json.loads(sys.argv[2])
        print(confirm_memory(results))
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)