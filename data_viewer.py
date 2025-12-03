"""
Math Stack Exchange 数据查看器
支持Web界面和命令行界面
展示爬取的题目、答案，支持随机展示、跳转、搜索等功能
"""

import sqlite3
import json
import random
import os
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import re

# Web界面相关
try:
    from flask import Flask, render_template_string, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("警告: Flask未安装，Web界面不可用。使用 'pip install flask' 安装。")

# 命令行界面相关
try:
    import rich
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Prompt, IntPrompt, Confirm
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("警告: Rich未安装，命令行界面简化。使用 'pip install rich' 获得更好体验。")

@dataclass
class Question:
    """问题数据结构"""
    question_id: int
    title: str
    body: str
    tags: List[str]
    score: int
    view_count: int
    answer_count: int
    creation_date: str
    last_activity_date: str
    owner: Dict
    link: str
    is_answered: bool
    accepted_answer_id: Optional[int] = None
    answers: List[Dict] = None

@dataclass
class Answer:
    """答案数据结构"""
    answer_id: int
    question_id: int
    body: str
    score: int
    creation_date: str
    last_activity_date: str
    owner: Dict
    is_accepted: bool

class DatabaseManager:
    """数据库管理类"""

    def __init__(self, db_path: str = "math_se_data/math_se_questions.db"):
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使用字典形式访问行
        return conn

    def get_question_count(self) -> int:
        """获取问题总数"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions")
        result = cursor.fetchone()[0]
        conn.close()
        return result

    def get_answer_count(self) -> int:
        """获取答案总数"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM answers")
        result = cursor.fetchone()[0]
        conn.close()
        return result

    def get_question_by_id(self, question_id: int) -> Optional[Question]:
        """根据ID获取问题"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM questions WHERE question_id = ?
        """, (question_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        # 获取答案
        cursor.execute("""
            SELECT * FROM answers WHERE question_id = ? ORDER BY score DESC
        """, (question_id,))

        answer_rows = cursor.fetchall()
        answers = []
        for answer_row in answer_rows:
            answers.append({
                'answer_id': answer_row['answer_id'],
                'body': answer_row['body'],
                'score': answer_row['score'],
                'creation_date': answer_row['creation_date'],
                'last_activity_date': answer_row['last_activity_date'],
                'owner': json.loads(answer_row['owner']) if answer_row['owner'] else {},
                'is_accepted': bool(answer_row['is_accepted'])
            })

        conn.close()

        # 构建问题对象
        question = Question(
            question_id=row['question_id'],
            title=row['title'],
            body=row['body'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            score=row['score'],
            view_count=row['view_count'],
            answer_count=row['answer_count'],
            creation_date=row['creation_date'],
            last_activity_date=row['last_activity_date'],
            owner=json.loads(row['owner']) if row['owner'] else {},
            link=row['link'],
            is_answered=bool(row['is_answered']),
            accepted_answer_id=row['accepted_answer_id'],
            answers=answers
        )

        return question

    def get_question_by_index(self, index: int) -> Optional[Question]:
        """根据索引获取问题（0-based）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT question_id FROM questions
            ORDER BY question_id
            LIMIT 1 OFFSET ?
        """, (index,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        question_id = row['question_id']
        conn.close()

        return self.get_question_by_id(question_id)

    def get_random_question(self) -> Optional[Question]:
        """获取随机问题"""
        count = self.get_question_count()
        if count == 0:
            return None

        random_index = random.randint(0, count - 1)
        return self.get_question_by_index(random_index)

    def search_questions(self, query: str, search_in: str = 'all') -> List[Question]:
        """搜索问题"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query_conditions = []
        params = []

        # 构建搜索条件
        if search_in in ['all', 'title']:
            query_conditions.append("title LIKE ?")
            params.append(f"%{query}%")

        if search_in in ['all', 'body']:
            query_conditions.append("body LIKE ?")
            params.append(f"%{query}%")

        if search_in in ['all', 'tags']:
            query_conditions.append("tags LIKE ?")
            params.append(f"%{query}%")

        where_clause = " OR ".join(query_conditions)

        cursor.execute(f"""
            SELECT question_id FROM questions
            WHERE {where_clause}
            ORDER BY score DESC, question_id DESC
            LIMIT 50
        """, params)

        rows = cursor.fetchall()
        conn.close()

        questions = []
        for row in rows:
            question = self.get_question_by_id(row['question_id'])
            if question:
                questions.append(question)

        return questions

    def get_questions_by_tags(self, tags: List[str]) -> List[Question]:
        """根据标签获取问题"""
        conn = self.get_connection()
        cursor = conn.cursor()

        tag_conditions = []
        params = []

        for tag in tags:
            tag_conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")

        where_clause = " OR ".join(tag_conditions)

        cursor.execute(f"""
            SELECT question_id FROM questions
            WHERE {where_clause}
            ORDER BY creation_date DESC
            LIMIT 100
        """, params)

        rows = cursor.fetchall()
        conn.close()

        questions = []
        for row in rows:
            question = self.get_question_by_id(row['question_id'])
            if question:
                questions.append(question)

        return questions

    def get_top_questions(self, limit: int = 20, sort_by: str = 'score') -> List[Question]:
        """获取热门问题"""
        conn = self.get_connection()
        cursor = conn.cursor()

        order_by_map = {
            'score': 'score DESC',
            'views': 'view_count DESC',
            'answers': 'answer_count DESC',
            'recent': 'creation_date DESC'
        }

        order_clause = order_by_map.get(sort_by, 'score DESC')

        cursor.execute(f"""
            SELECT question_id FROM questions
            ORDER BY {order_clause}
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        questions = []
        for row in rows:
            question = self.get_question_by_id(row['question_id'])
            if question:
                questions.append(question)

        return questions

    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 基本统计
        cursor.execute("SELECT COUNT(*) FROM questions")
        total_questions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM answers")
        total_answers = cursor.fetchone()[0]

        # 分数统计
        cursor.execute("""
            SELECT AVG(score), MAX(score), MIN(score)
            FROM questions
        """)
        score_stats = cursor.fetchone()

        # 标签统计
        cursor.execute("SELECT tags FROM questions")
        tag_rows = cursor.fetchall()
        tag_counts = defaultdict(int)
        for row in tag_rows:
            tags = json.loads(row['tags']) if row['tags'] else []
            for tag in tags:
                tag_counts[tag] += 1

        # 时间统计
        cursor.execute("""
            SELECT MIN(creation_date), MAX(creation_date)
            FROM questions
            WHERE creation_date IS NOT NULL
        """)
        date_stats = cursor.fetchone()

        # 有答案的问题统计
        cursor.execute("SELECT COUNT(*) FROM questions WHERE is_answered = 1")
        answered_questions = cursor.fetchone()[0]

        conn.close()

        # 获取热门标签
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'total_questions': total_questions,
            'total_answers': total_answers,
            'answered_questions': answered_questions,
            'average_score': round(score_stats[0] or 0, 2),
            'max_score': score_stats[1] or 0,
            'min_score': score_stats[2] or 0,
            'top_tags': top_tags,
            'earliest_date': date_stats[0],
            'latest_date': date_stats[1],
            'total_unique_tags': len(tag_counts)
        }

class DataViewer:
    """数据查看器主类"""

    def __init__(self, db_path: str = "math_se_data/math_se_questions.db"):
        self.db_manager = DatabaseManager(db_path)
        self.console = Console() if RICH_AVAILABLE else None

    def format_text(self, text: str, max_length: int = 200) -> str:
        """格式化文本，去除HTML标签并限制长度"""
        if not text:
            return ""

        # 简单的HTML标签移除
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&[^;]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text

    def render_question_rich(self, question: Question) -> None:
        """使用Rich渲染问题"""
        if not RICH_AVAILABLE:
            self.render_question_simple(question)
            return

        # 问题标题
        title_text = Text(f"问题 #{question.question_id}: {question.title}", style="bold blue")
        self.console.print(Panel(title_text, title="Math Stack Exchange Question"))

        # 问题信息
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="green")

        info_table.add_row("分数", str(question.score))
        info_table.add_row("浏览次数", str(question.view_count))
        info_table.add_row("答案数量", str(question.answer_count))
        info_table.add_row("创建时间", question.creation_date)
        info_table.add_row("标签", ", ".join(question.tags))

        if question.owner:
            owner_name = question.owner.get('display_name', 'Unknown')
            owner_reputation = question.owner.get('reputation', 0)
            info_table.add_row("作者", f"{owner_name} (声誉: {owner_reputation})")

        info_table.add_row("链接", question.link)

        self.console.print(info_table)
        self.console.print()

        # 问题内容（摘要）
        body_preview = self.format_text(question.body, 500)
        self.console.print(Panel(body_preview, title="问题内容 (摘要)"))
        self.console.print()

        # 答案
        if question.answers:
            self.console.print(f"[bold]答案 ({len(question.answers)}):[/bold]")
            for i, answer in enumerate(question.answers, 1):
                answer_status = "✓ 已采纳" if answer['is_accepted'] else ""
                answer_title = f"答案 #{i} {answer_status}"
                answer_info = f"分数: {answer['score']} | 创建时间: {answer['creation_date']}"

                answer_preview = self.format_text(answer['body'], 300)
                self.console.print(Panel(
                    answer_preview,
                    title=f"{answer_title}\n{answer_info}",
                    border_style="green" if answer['is_accepted'] else "blue"
                ))
        else:
            self.console.print("[yellow]暂无答案[/yellow]")

    def render_question_simple(self, question: Question) -> None:
        """简单文本渲染问题"""
        print(f"\n{'='*60}")
        print(f"问题 #{question.question_id}: {question.title}")
        print(f"{'='*60}")
        print(f"分数: {question.score} | 浏览: {question.view_count} | 答案: {question.answer_count}")
        print(f"标签: {', '.join(question.tags)}")
        if question.owner:
            print(f"作者: {question.owner.get('display_name', 'Unknown')}")
        print(f"链接: {question.link}")
        print(f"创建时间: {question.creation_date}")
        print(f"\n问题内容:")
        body_preview = self.format_text(question.body, 500)
        print(body_preview)

        if question.answers:
            print(f"\n答案 ({len(question.answers)}):")
            for i, answer in enumerate(question.answers, 1):
                status = "[已采纳]" if answer['is_accepted'] else ""
                print(f"\n--- 答案 #{i} {status} (分数: {answer['score']}) ---")
                answer_preview = self.format_text(answer['body'], 300)
                print(answer_preview)
        else:
            print("\n暂无答案")

    def show_question_by_id(self, question_id: int) -> bool:
        """根据ID显示问题"""
        question = self.db_manager.get_question_by_id(question_id)
        if not question:
            if self.console:
                self.console.print(f"[red]问题 #{question_id} 不存在[/red]")
            else:
                print(f"问题 #{question_id} 不存在")
            return False

        self.render_question_rich(question) if RICH_AVAILABLE else self.render_question_simple(question)
        return True

    def show_question_by_index(self, index: int) -> bool:
        """根据索引显示问题"""
        question = self.db_manager.get_question_by_index(index)
        if not question:
            if self.console:
                self.console.print(f"[red]索引 {index} 无效[/red]")
            else:
                print(f"索引 {index} 无效")
            return False

        if self.console:
            self.console.print(f"[cyan]索引 {index} 对应问题 #{question.question_id}[/cyan]")

        self.render_question_rich(question) if RICH_AVAILABLE else self.render_question_simple(question)
        return True

    def show_random_question(self) -> bool:
        """显示随机问题"""
        question = self.db_manager.get_random_question()
        if not question:
            if self.console:
                self.console.print("[red]数据库中没有问题[/red]")
            else:
                print("数据库中没有问题")
            return False

        if self.console:
            self.console.print("[yellow]随机问题:[/yellow]")

        self.render_question_rich(question) if RICH_AVAILABLE else self.render_question_simple(question)
        return True

    def search_and_show(self, query: str, search_in: str = 'all') -> int:
        """搜索并显示问题"""
        questions = self.db_manager.search_questions(query, search_in)

        if not questions:
            if self.console:
                self.console.print(f"[red]没有找到包含 '{query}' 的问题[/red]")
            else:
                print(f"没有找到包含 '{query}' 的问题")
            return 0

        if self.console:
            self.console.print(f"[green]找到 {len(questions)} 个包含 '{query}' 的问题:[/green]")
        else:
            print(f"\n找到 {len(questions)} 个包含 '{query}' 的问题:")

        # 显示问题列表
        for i, question in enumerate(questions, 1):
            score_info = f"(分数: {question.score}, 答案: {question.answer_count})"
            tags_info = f"[{', '.join(question.tags)}]" if question.tags else ""

            if self.console:
                self.console.print(f"{i:2d}. #{question.question_id} {question.title[:50]}... {score_info} {tags_info}")
            else:
                print(f"{i:2d}. #{question.question_id} {question.title[:50]}... {score_info} {tags_info}")

        return len(questions)

    def show_top_questions(self, limit: int = 10, sort_by: str = 'score'):
        """显示热门问题"""
        questions = self.db_manager.get_top_questions(limit, sort_by)

        if not questions:
            if self.console:
                self.console.print("[red]数据库中没有问题[/red]")
            else:
                print("数据库中没有问题")
            return

        sort_name = {
            'score': '分数',
            'views': '浏览次数',
            'answers': '答案数量',
            'recent': '最新'
        }.get(sort_by, '分数')

        if self.console:
            self.console.print(f"[green]Top {limit} 问题 (按{sort_name}排序):[/green]")
        else:
            print(f"\nTop {limit} 问题 (按{sort_name}排序):")

        for i, question in enumerate(questions, 1):
            tags_info = f"[{', '.join(question.tags[:3])}]" if question.tags else ""
            if self.console:
                self.console.print(f"{i:2d}. #{question.question_id} {question.title[:40]}... (分数: {question.score}) {tags_info}")
            else:
                print(f"{i:2d}. #{question.question_id} {question.title[:40]}... (分数: {question.score}) {tags_info}")

    def show_statistics(self):
        """显示数据库统计信息"""
        stats = self.db_manager.get_statistics()

        if self.console:
            # 使用Rich展示统计信息
            stats_table = Table(title="数据库统计信息")
            stats_table.add_column("指标", style="cyan")
            stats_table.add_column("数值", style="green")

            stats_table.add_row("总问题数", str(stats['total_questions']))
            stats_table.add_row("总答案数", str(stats['total_answers']))
            stats_table.add_row("有答案的问题数", str(stats['answered_questions']))
            stats_table.add_row("平均分数", str(stats['average_score']))
            stats_table.add_row("最高分数", str(stats['max_score']))
            stats_table.add_row("最低分数", str(stats['min_score']))
            stats_table.add_row("唯一标签数", str(stats['total_unique_tags']))

            if stats['earliest_date']:
                stats_table.add_row("最早问题时间", stats['earliest_date'])
            if stats['latest_date']:
                stats_table.add_row("最新问题时间", stats['latest_date'])

            self.console.print(stats_table)

            # 显示热门标签
            if stats['top_tags']:
                self.console.print("\n[bold]热门标签:[/bold]")
                tag_table = Table(show_header=True)
                tag_table.add_column("标签", style="blue")
                tag_table.add_column("使用次数", style="yellow")

                for tag, count in stats['top_tags']:
                    tag_table.add_row(tag, str(count))

                self.console.print(tag_table)
        else:
            # 简单文本输出
            print("\n数据库统计信息:")
            print(f"总问题数: {stats['total_questions']}")
            print(f"总答案数: {stats['total_answers']}")
            print(f"有答案的问题数: {stats['answered_questions']}")
            print(f"平均分数: {stats['average_score']}")
            print(f"最高分数: {stats['max_score']}")
            print(f"最低分数: {stats['min_score']}")
            print(f"唯一标签数: {stats['total_unique_tags']}")

            if stats['top_tags']:
                print("\n热门标签:")
                for tag, count in stats['top_tags']:
                    print(f"  {tag}: {count}")

    def interactive_mode(self):
        """交互式模式"""
        if not RICH_AVAILABLE:
            print("警告: Rich库未安装，交互体验简化")

        print("\n=== Math Stack Exchange 数据查看器 ===")
        self.show_statistics()

        while True:
            print("\n可用命令:")
            print("  id <问题ID>    - 查看指定ID的问题")
            print("  index <索引>   - 查看指定索引的问题 (0-based)")
            print("  random         - 随机问题")
            print("  search <关键词> - 搜索问题")
            print("  tags <标签>    - 按标签查看问题")
            print("  top <数量>     - 查看热门问题")
            print("  stats          - 显示统计信息")
            print("  quit/exit      - 退出")

            try:
                if RICH_AVAILABLE:
                    command = Prompt.ask("[bold cyan]请输入命令[/bold cyan]")
                else:
                    command = input("请输入命令: ").strip()

                if not command:
                    continue

                parts = command.split()
                cmd = parts[0].lower()

                if cmd in ['quit', 'exit', 'q']:
                    print("再见!")
                    break
                elif cmd == 'id' and len(parts) >= 2:
                    try:
                        question_id = int(parts[1])
                        self.show_question_by_id(question_id)
                    except ValueError:
                        print("错误: 请输入有效的问题ID")
                elif cmd == 'index' and len(parts) >= 2:
                    try:
                        index = int(parts[1])
                        self.show_question_by_index(index)
                    except ValueError:
                        print("错误: 请输入有效的索引")
                elif cmd == 'random':
                    self.show_random_question()
                elif cmd == 'search' and len(parts) >= 2:
                    query = ' '.join(parts[1:])
                    self.search_and_show(query)
                elif cmd == 'tags' and len(parts) >= 2:
                    tags = parts[1:]
                    questions = self.db_manager.get_questions_by_tags(tags)
                    if RICH_AVAILABLE:
                        self.console.print(f"[green]找到 {len(questions)} 个包含标签 {tags} 的问题:[/green]")
                    else:
                        print(f"\n找到 {len(questions)} 个包含标签 {tags} 的问题:")

                    for i, question in enumerate(questions[:10], 1):
                        if RICH_AVAILABLE:
                            self.console.print(f"{i}. #{question.question_id} {question.title[:50]}...")
                        else:
                            print(f"{i}. #{question.question_id} {question.title[:50]}...")
                elif cmd == 'top':
                    limit = int(parts[1]) if len(parts) >= 2 else 10
                    self.show_top_questions(limit)
                elif cmd == 'stats':
                    self.show_statistics()
                else:
                    print("未知命令，请重试")

            except KeyboardInterrupt:
                print("\n\n再见!")
                break
            except Exception as e:
                print(f"错误: {e}")

class WebDataViewer:
    """Web界面数据查看器"""

    def __init__(self, db_path: str = "math_se_data/math_se_questions.db"):
        if not FLASK_AVAILABLE:
            raise ImportError("Flask未安装，无法使用Web界面")

        self.db_manager = DatabaseManager(db_path)
        self.app = Flask(__name__)
        self.setup_routes()

    def setup_routes(self):
        """设置路由"""

        @self.app.route('/')
        def index():
            return self.render_index_template()

        @self.app.route('/question/<int:question_id>')
        def show_question(question_id):
            return self.render_question_template(question_id)

        @self.app.route('/random')
        def random_question():
            question = self.db_manager.get_random_question()
            if question:
                return self.render_question_template(question.question_id)
            return "数据库中没有问题", 404

        @self.app.route('/search')
        def search():
            query = request.args.get('q', '')
            search_in = request.args.get('in', 'all')

            if not query:
                return redirect('/')

            questions = self.db_manager.search_questions(query, search_in)
            return self.render_search_results_template(query, questions)

        @self.app.route('/api/stats')
        def api_stats():
            return jsonify(self.db_manager.get_statistics())

        @self.app.route('/api/question/<int:question_id>')
        def api_question(question_id):
            question = self.db_manager.get_question_by_id(question_id)
            if question:
                # 转换为JSON可序列化格式
                return {
                    'question_id': question.question_id,
                    'title': question.title,
                    'body': question.body,
                    'tags': question.tags,
                    'score': question.score,
                    'view_count': question.view_count,
                    'answer_count': question.answer_count,
                    'creation_date': question.creation_date,
                    'link': question.link,
                    'answers': question.answers
                }
            return jsonify({'error': 'Question not found'}), 404

    def render_index_template(self):
        """渲染首页模板"""
        stats = self.db_manager.get_statistics()
        top_questions = self.db_manager.get_top_questions(10)

        template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Math Stack Exchange 数据查看器</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-card { background: #f0f0f0; padding: 15px; border-radius: 5px; flex: 1; }
        .question-list { list-style: none; padding: 0; }
        .question-item { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .question-title { font-weight: bold; color: #0066cc; text-decoration: none; }
        .question-meta { color: #666; font-size: 0.9em; margin-top: 5px; }
        .search-box { margin: 20px 0; }
        .search-box input { padding: 8px; width: 300px; }
        .search-box button { padding: 8px 15px; background: #0066cc; color: white; border: none; cursor: pointer; }
        .tag { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }
        .nav-buttons { margin: 20px 0; }
        .nav-buttons button { margin: 5px; padding: 10px 15px; background: #0066cc; color: white; border: none; border-radius: 3px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>Math Stack Exchange 数据查看器</h1>

    <div class="nav-buttons">
        <button onclick="location.href='/random'">随机问题</button>
        <button onclick="location.href='javascript:search()'">搜索问题</button>
    </div>

    <div class="search-box">
        <input type="text" id="searchInput" placeholder="搜索问题..." onkeypress="if(event.key==='Enter') search()">
        <button onclick="search()">搜索</button>
    </div>

    <div class="stats">
        <div class="stat-card">
            <h3>总问题数</h3>
            <p>{{ total_questions }}</p>
        </div>
        <div class="stat-card">
            <h3>总答案数</h3>
            <p>{{ total_answers }}</p>
        </div>
        <div class="stat-card">
            <h3>有答案问题</h3>
            <p>{{ answered_questions }}</p>
        </div>
        <div class="stat-card">
            <h3>平均分数</h3>
            <p>{{ average_score }}</p>
        </div>
    </div>

    <h2>热门问题</h2>
    <ul class="question-list">
        {% for question in top_questions %}
        <li class="question-item">
            <a href="/question/{{ question.question_id }}" class="question-title">
                {{ question.title }}
            </a>
            <div class="question-meta">
                问题 #{{ question.question_id }} |
                分数: {{ question.score }} |
                答案: {{ question.answer_count }} |
                浏览: {{ question.view_count }}
                {% if question.tags %}
                | 标签:
                {% for tag in question.tags[:3] %}
                <span class="tag">{{ tag }}</span>
                {% endfor %}
                {% endif %}
            </div>
        </li>
        {% endfor %}
    </ul>

    <script>
        function search() {
            const query = document.getElementById('searchInput').value.trim();
            if (query) {
                location.href = '/search?q=' + encodeURIComponent(query);
            }
        }
    </script>
</body>
</html>
        '''

        from flask import render_template_string
        return render_template_string(template, **stats, top_questions=top_questions)

    def render_question_template(self, question_id):
        """渲染问题页面模板"""
        question = self.db_manager.get_question_by_id(question_id)
        if not question:
            return "问题不存在", 404

        template = '''
<!DOCTYPE html>
<html>
<head>
    <title>问题 #{{ question.question_id }} - Math Stack Exchange</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; line-height: 1.6; }
        .question-header { background: #f8f8f8; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .question-title { font-size: 1.5em; font-weight: bold; margin-bottom: 10px; color: #333; }
        .question-meta { color: #666; font-size: 0.9em; }
        .question-body { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        .answer { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        .accepted-answer { border-left: 5px solid #28a745; }
        .answer-header { font-weight: bold; margin-bottom: 10px; }
        .answer-meta { color: #666; font-size: 0.9em; margin-bottom: 10px; }
        .tag { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; margin-right: 3px; }
        .nav-buttons { margin: 20px 0; }
        .nav-buttons button { margin: 5px; padding: 10px 15px; background: #0066cc; color: white; border: none; border-radius: 3px; cursor: pointer; }
        .link { color: #0066cc; text-decoration: none; }
        .link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="nav-buttons">
        <button onclick="history.back()">← 返回</button>
        <button onclick="location.href='/'">首页</button>
        <button onclick="location.href='/random'">随机问题</button>
    </div>

    <div class="question-header">
        <div class="question-title">问题 #{{ question.question_id }}: {{ question.title }}</div>
        <div class="question-meta">
            分数: <strong>{{ question.score }}</strong> |
            浏览: {{ question.view_count }} |
            答案: {{ question.answer_count }} |
            创建时间: {{ question.creation_date }} |
            <a href="{{ question.link }}" class="link" target="_blank">查看原文</a>
        </div>
        {% if question.tags %}
        <div style="margin-top: 10px;">
            标签:
            {% for tag in question.tags %}
            <span class="tag">{{ tag }}</span>
            {% endfor %}
        </div>
        {% endif %}
    </div>

    <div class="question-body">
        {{ question.body | safe }}
    </div>

    <h2>答案 ({{ answers|length }})</h2>
    {% for answer in answers %}
    <div class="answer {% if answer.is_accepted %}accepted-answer{% endif %}">
        <div class="answer-header">
            答案 #{{ loop.index }} {% if answer.is_accepted %}✓ 已采纳{% endif %}
        </div>
        <div class="answer-meta">
            分数: <strong>{{ answer.score }}</strong> |
            创建时间: {{ answer.creation_date }}
        </div>
        <div>{{ answer.body | safe }}</div>
    </div>
    {% else %}
    <p>暂无答案</p>
    {% endfor %}

    <div class="nav-buttons" style="margin-top: 30px;">
        <button onclick="history.back()">← 返回</button>
        <button onclick="location.href='/'">首页</button>
        <button onclick="location.href='/random'">随机问题</button>
    </div>
</body>
</html>
        '''

        from flask import render_template_string
        return render_template_string(template, question=question, answers=question.answers or [])

    def render_search_results_template(self, query, questions):
        """渲染搜索结果模板"""
        template = '''
<!DOCTYPE html>
<html>
<head>
    <title>搜索结果: "{{ query }}" - Math Stack Exchange</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }
        .search-header { margin-bottom: 20px; }
        .question-list { list-style: none; padding: 0; }
        .question-item { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .question-title { font-weight: bold; color: #0066cc; text-decoration: none; font-size: 1.1em; }
        .question-meta { color: #666; font-size: 0.9em; margin-top: 5px; }
        .tag { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; margin-right: 3px; }
        .search-box { margin: 20px 0; }
        .search-box input { padding: 8px; width: 300px; }
        .search-box button { padding: 8px 15px; background: #0066cc; color: white; border: none; cursor: pointer; }
        .nav-buttons { margin: 20px 0; }
        .nav-buttons button { margin: 5px; padding: 10px 15px; background: #0066cc; color: white; border: none; border-radius: 3px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="nav-buttons">
        <button onclick="location.href='/'">首页</button>
        <button onclick="location.href='/random'">随机问题</button>
    </div>

    <div class="search-header">
        <h1>搜索结果: "{{ query }}"</h1>
        <p>找到 {{ count }} 个问题</p>

        <div class="search-box">
            <input type="text" id="searchInput" value="{{ query }}" placeholder="搜索问题..." onkeypress="if(event.key==='Enter') search()">
            <button onclick="search()">搜索</button>
        </div>
    </div>

    <ul class="question-list">
        {% for question in questions %}
        <li class="question-item">
            <a href="/question/{{ question.question_id }}" class="question-title">
                {{ question.title }}
            </a>
            <div class="question-meta">
                问题 #{{ question.question_id }} |
                分数: {{ question.score }} |
                答案: {{ question.answer_count }} |
                浏览: {{ question.view_count }}
                {% if question.tags %}
                | 标签:
                {% for tag in question.tags[:5] %}
                <span class="tag">{{ tag }}</span>
                {% endfor %}
                {% endif %}
            </div>
        </li>
        {% endfor %}
    </ul>

    {% if questions|length == 0 %}
    <p>没有找到相关问题。请尝试其他关键词。</p>
    {% endif %}

    <script>
        function search() {
            const query = document.getElementById('searchInput').value.trim();
            if (query) {
                location.href = '/search?q=' + encodeURIComponent(query);
            }
        }
    </script>
</body>
</html>
        '''

        from flask import render_template_string
        return render_template_string(template, query=query, questions=questions, count=len(questions))

    def run(self, host='127.0.0.1', port=5000, debug=False):
        """运行Web服务器"""
        print(f"启动Web数据查看器...")
        print(f"访问地址: http://{host}:{port}")
        print("按 Ctrl+C 停止服务器")

        try:
            self.app.run(host=host, port=port, debug=debug)
        except KeyboardInterrupt:
            print("\nWeb服务器已停止")

def main():
    parser = argparse.ArgumentParser(description='Math Stack Exchange 数据查看器')
    parser.add_argument('mode', choices=['cli', 'web'], default='cli',
                       help='运行模式: cli(命令行) 或 web(Web界面)')
    parser.add_argument('--db', default='math_se_data/math_se_questions.db',
                       help='数据库文件路径')
    parser.add_argument('--id', type=int,
                       help='直接查看指定ID的问题')
    parser.add_argument('--index', type=int,
                       help='查看指定索引的问题 (0-based)')
    parser.add_argument('--random', action='store_true',
                       help='显示随机问题')
    parser.add_argument('--search',
                       help='搜索问题')
    parser.add_argument('--top', type=int, default=10,
                       help='显示热门问题数量')
    parser.add_argument('--stats', action='store_true',
                       help='显示统计信息')
    parser.add_argument('--tags', nargs='*',
                       help='按标签查看问题')
    parser.add_argument('--host', default='127.0.0.1',
                       help='Web服务器主机地址')
    parser.add_argument('--port', type=int, default=5000,
                       help='Web服务器端口')
    parser.add_argument('--debug', action='store_true',
                       help='Web服务器调试模式')

    args = parser.parse_args()

    try:
        if args.mode == 'cli':
            viewer = DataViewer(args.db)

            # 直接执行指定操作
            if args.id:
                viewer.show_question_by_id(args.id)
            elif args.index is not None:
                viewer.show_question_by_index(args.index)
            elif args.random:
                viewer.show_random_question()
            elif args.search:
                viewer.search_and_show(args.search)
            elif args.stats:
                viewer.show_statistics()
            elif args.tags:
                questions = viewer.db_manager.get_questions_by_tags(args.tags)
                print(f"找到 {len(questions)} 个包含标签 {args.tags} 的问题:")
                for i, question in enumerate(questions[:10], 1):
                    print(f"{i}. #{question.question_id} {question.title[:50]}...")
            else:
                # 交互式模式
                viewer.interactive_mode()

        elif args.mode == 'web':
            if not FLASK_AVAILABLE:
                print("错误: Flask未安装，无法使用Web界面")
                print("请运行: pip install flask")
                return

            web_viewer = WebDataViewer(args.db)
            web_viewer.run(host=args.host, port=args.port, debug=args.debug)

    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请确保数据库文件存在，或先运行爬虫获取数据")
    except Exception as e:
        print(f"运行错误: {e}")

if __name__ == '__main__':
    main()