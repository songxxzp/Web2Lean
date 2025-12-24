"""
Math Stack Exchange 数据更新器 (修复版)
支持增量更新新答案和采纳状态，保留历史数据
"""

import sqlite3
import json
import time
import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
import shutil
from pathlib import Path

from math_se_crawler import MathSECrawler, CrawlerConfig, CrawlerState, Question, Answer
from crawler_config import CrawlerConfig as Config

@dataclass
class UpdateRecord:
    """数据更新记录"""
    update_id: str
    update_time: str
    update_mode: str
    questions_updated: int
    answers_added: int
    acceptances_updated: int
    questions_processed: int
    duration_seconds: float
    details: str

class HistoryManager:
    """历史数据管理器"""

    def __init__(self, history_db_path: str = "math_se_data/history.db"):
        self.history_db_path = history_db_path
        self.init_history_database()

    def init_history_database(self):
        """初始化历史数据库"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        # 创建与主数据库结构一致的表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER,
                title TEXT,
                body TEXT,
                tags TEXT,
                score INTEGER,
                view_count INTEGER,
                answer_count INTEGER,
                creation_date TEXT,
                last_activity_date TEXT,
                owner TEXT,
                link TEXT,
                is_answered BOOLEAN,
                accepted_answer_id INTEGER,
                first_seen_date TEXT,
                last_seen_date TEXT,
                update_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'historical',
                update_id TEXT,
                PRIMARY KEY (question_id, update_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS answers (
                answer_id INTEGER,
                question_id INTEGER,
                body TEXT,
                score INTEGER,
                creation_date TEXT,
                last_activity_date TEXT,
                owner TEXT,
                is_accepted BOOLEAN,
                first_seen_date TEXT,
                last_seen_date TEXT,
                update_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'historical',
                update_id TEXT,
                PRIMARY KEY (answer_id, update_id)
            )
        ''')

        # 创建更新记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_records (
                update_id TEXT PRIMARY KEY,
                update_time TEXT,
                update_mode TEXT,
                questions_updated INTEGER,
                answers_added INTEGER,
                acceptances_updated INTEGER,
                questions_processed INTEGER,
                duration_seconds REAL,
                details TEXT
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_questions_id ON questions(question_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_answers_id ON answers(question_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_updates_time ON update_records(update_time)')

        conn.commit()
        conn.close()

    def save_update_record(self, record: UpdateRecord):
        """保存更新记录"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO update_records
            (update_id, update_time, update_mode, questions_updated, answers_added,
             acceptances_updated, questions_processed, duration_seconds, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.update_id,
            record.update_time,
            record.update_mode,
            record.questions_updated,
            record.answers_added,
            record.acceptances_updated,
            record.questions_processed,
            record.duration_seconds,
            record.details
        ))

        conn.commit()
        conn.close()

    def archive_current_data(self, main_db_path: str, update_id: str):
        """将当前数据存档到历史数据库"""
        main_conn = sqlite3.connect(main_db_path)
        hist_conn = sqlite3.connect(self.history_db_path)

        main_cursor = main_conn.cursor()
        hist_cursor = hist_conn.cursor()

        try:
            # 获取问题数据 - 使用索引位置
            main_cursor.execute("SELECT * FROM questions")
            for row in main_cursor.fetchall():
                hist_cursor.execute('''
                    INSERT OR REPLACE INTO questions
                    (question_id, title, body, tags, score, view_count, answer_count,
                     creation_date, last_activity_date, owner, link, is_answered,
                     accepted_answer_id, first_seen_date, last_seen_date,
                     update_count, status, update_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                    row[7], row[8], row[9], row[10], row[11], row[12], row[13],
                    row[7], row[8], 1, 'historical', update_id
                ))

            # 获取答案数据 - 使用索引位置
            main_cursor.execute("SELECT * FROM answers")
            for row in main_cursor.fetchall():
                hist_cursor.execute('''
                    INSERT OR REPLACE INTO answers
                    (answer_id, question_id, body, score, creation_date,
                     last_activity_date, owner, is_accepted, first_seen_date,
                     last_seen_date, update_count, status, update_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'historical', ?)
                ''', (
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7],
                    row[4], row[5], update_id
                ))

            hist_conn.commit()
            print(f"已存档数据到历史数据库，更新ID: {update_id}")

        except Exception as e:
            print(f"存档数据失败: {e}")
            raise
        finally:
            main_conn.close()
            hist_conn.close()

    def get_history_stats(self) -> Dict:
        """获取历史数据统计"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        # 获取更新记录数
        cursor.execute("SELECT COUNT(*) FROM update_records")
        update_count = cursor.fetchone()[0]

        # 获取总历史问题数
        cursor.execute("SELECT COUNT(DISTINCT question_id) FROM questions")
        total_questions = cursor.fetchone()[0]

        # 获取总历史答案数
        cursor.execute("SELECT COUNT(DISTINCT answer_id) FROM answers")
        total_answers = cursor.fetchone()[0]

        # 获取最近更新
        cursor.execute("SELECT * FROM update_records ORDER BY update_time DESC LIMIT 5")
        recent_updates = cursor.fetchall()

        conn.close()

        return {
            'update_count': update_count,
            'total_questions': total_questions,
            'total_answers': total_answers,
            'recent_updates': [dict(zip([col[0] for col in cursor.description], row)) for row in recent_updates]
        }

class DataUpdater:
    """数据更新器主类"""

    def __init__(self, main_db_path: str = "math_se_questions.db",
                 history_db_path: str = "math_se_history.db"):
        self.main_db_path = main_db_path
        self.history_db_path = history_db_path
        self.history_manager = HistoryManager(history_db_path)

        # 初始化爬虫配置
        self.config = Config("crawler_config.json")
        self.crawler = MathSECrawler(self.config)

        self.update_id = f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def get_main_db_connection(self) -> sqlite3.Connection:
        """获取主数据库连接"""
        conn = sqlite3.connect(self.main_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_question_ids(self) -> Set[int]:
        """获取所有问题ID"""
        conn = self.get_main_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT question_id FROM questions")
        ids = {row['question_id'] for row in cursor.fetchall()}
        conn.close()
        return ids

    def get_unanswered_questions(self) -> List[int]:
        """获取未回答的问题ID列表"""
        conn = self.get_main_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT question_id FROM questions WHERE answer_count = 0 OR is_answered = 0")
        ids = [row['question_id'] for row in cursor.fetchall()]
        conn.close()
        return ids

    def get_questions_without_accepted_answer(self) -> List[int]:
        """获取没有采纳答案的问题ID列表"""
        conn = self.get_main_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT question_id FROM questions WHERE answer_count > 0 AND (accepted_answer_id IS NULL OR accepted_answer_id = 0)")
        ids = [row['question_id'] for row in cursor.fetchall()]
        conn.close()
        return ids

    def get_zero_answer_questions(self) -> List[int]:
        """获取零答案的问题ID列表"""
        conn = self.get_main_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT question_id FROM questions WHERE answer_count = 0")
        ids = [row['question_id'] for row in cursor.fetchall()]
        conn.close()
        return ids

    def check_question_updates(self, question_id: int) -> Tuple[bool, Question, List[Answer]]:
        """检查问题是否有更新"""
        # 获取最新的问题数据
        from data_viewer import DatabaseManager
        db_manager = DatabaseManager(self.config.get('db_path', 'math_se_data/math_se_questions.db'))
        latest_question = db_manager.get_question_by_id(question_id)
        if not latest_question:
            return False, None, []

        # 获取当前数据库中的数据
        conn = self.get_main_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM questions WHERE question_id = ?", (question_id,))
        current_row = cursor.fetchone()

        if not current_row:
            conn.close()
            return True, latest_question, latest_question.answers or []

        # 检查关键字段是否有变化
        current_data = {
            'score': current_row['score'],
            'view_count': current_row['view_count'],
            'answer_count': current_row['answer_count'],
            'last_activity_date': current_row['last_activity_date'],
            'is_answered': bool(current_row['is_answered']),
            'accepted_answer_id': current_row['accepted_answer_id']
        }

        latest_data = {
            'score': latest_question.score,
            'view_count': latest_question.view_count,
            'answer_count': latest_question.answer_count,
            'last_activity_date': latest_question.last_activity_date,
            'is_answered': latest_question.is_answered,
            'accepted_answer_id': latest_question.accepted_answer_id
        }

        # 获取当前答案数量
        cursor.execute("SELECT COUNT(*) FROM answers WHERE question_id = ?", (question_id,))
        current_answer_count = cursor.fetchone()[0]
        latest_answer_count = len(latest_question.answers or [])

        conn.close()

        # 判断是否有更新
        has_updates = (
            current_data != latest_data or
            current_answer_count != latest_answer_count
        )

        return has_updates, latest_question, latest_question.answers or []

    def update_question_data(self, question: Question, answers: List[Answer]) -> bool:
        """更新问题和答案数据"""
        conn = self.get_main_db_connection()
        cursor = conn.cursor()

        try:
            # 更新问题数据
            cursor.execute('''
                UPDATE questions SET
                    title = ?, body = ?, tags = ?, score = ?, view_count = ?,
                    answer_count = ?, last_activity_date = ?, owner = ?,
                    link = ?, is_answered = ?, accepted_answer_id = ?
                WHERE question_id = ?
            ''', (
                question.title, question.body, json.dumps(question.tags),
                question.score, question.view_count, question.answer_count,
                question.last_activity_date, json.dumps(question.owner),
                question.link, question.is_answered, question.accepted_answer_id,
                question.question_id
            ))

            # 删除旧答案（因为可能有删除或修改）
            cursor.execute("DELETE FROM answers WHERE question_id = ?", (question.question_id,))

            # 插入新答案
            for answer in answers:
                cursor.execute('''
                    INSERT INTO answers
                    (answer_id, question_id, body, score, creation_date,
                     last_activity_date, owner, is_accepted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    answer.answer_id, answer.question_id, answer.body,
                    answer.score, answer.creation_date, answer.last_activity_date,
                    json.dumps(answer.owner), answer.is_accepted
                ))

            conn.commit()
            return True

        except Exception as e:
            print(f"更新问题 {question.question_id} 失败: {e}")
            conn.rollback()
            return False

    def run_full_update(self) -> UpdateRecord:
        """模式1: 重新访问所有问题，检查更新"""
        print("开始全量更新模式...")
        start_time = datetime.now()

        question_ids = list(self.get_all_question_ids())
        total_questions = len(question_ids)

        questions_updated = 0
        answers_added = 0
        acceptances_updated = 0

        print(f"需要检查 {total_questions} 个问题...")

        for i, question_id in enumerate(question_ids, 1):
            if i % 50 == 0:
                print(f"进度: {i}/{total_questions} ({i/total_questions:.1%})")

            has_updates, latest_question, answers = self.check_question_updates(question_id)

            if has_updates:
                if self.update_question_data(latest_question, answers):
                    questions_updated += 1
                    print(f"更新问题 #{question_id} (答案: {len(answers)})")

                    # 检查新答案数量
                    for answer in answers:
                        if answer.is_accepted:
                            acceptances_updated += 1
                    answers_added += len(answers)

            # 添加延迟避免API限制
            time.sleep(self.config.get('request_delay', 1.0))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        record = UpdateRecord(
            update_id=self.update_id,
            update_time=end_time.isoformat(),
            update_mode="full_update",
            questions_updated=questions_updated,
            answers_added=answers_added,
            acceptances_updated=acceptances_updated,
            questions_processed=total_questions,
            duration_seconds=duration,
            details=f"全量更新 {total_questions} 个问题"
        )

        return record

    def run_unanswered_update(self) -> UpdateRecord:
        """模式2: 重新访问未回答的问题"""
        print("开始未回答问题更新模式...")
        start_time = datetime.now()

        question_ids = self.get_unanswered_questions()
        total_questions = len(question_ids)

        questions_updated = 0
        answers_added = 0
        acceptances_updated = 0

        print(f"需要检查 {total_questions} 个未回答问题...")

        for i, question_id in enumerate(question_ids, 1):
            if i % 20 == 0:
                print(f"进度: {i}/{total_questions} ({i/total_questions:.1%})")

            has_updates, latest_question, answers = self.check_question_updates(question_id)

            if has_updates:
                if self.update_question_data(latest_question, answers):
                    questions_updated += 1
                    print(f"更新问题 #{question_id} (答案: {len(answers)})")

                    # 检查新答案数量和采纳
                    for answer in answers:
                        if answer.is_accepted:
                            acceptances_updated += 1
                    answers_added += len(answers)

            time.sleep(self.config.get('request_delay', 1.0))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        record = UpdateRecord(
            update_id=self.update_id,
            update_time=end_time.isoformat(),
            update_mode="unanswered_update",
            questions_updated=questions_updated,
            answers_added=answers_added,
            acceptances_updated=acceptances_updated,
            questions_processed=total_questions,
            duration_seconds=duration,
            details=f"未回答问题更新 {total_questions} 个问题"
        )

        return record

    def run_zero_answer_update(self) -> UpdateRecord:
        """模式3: 仅重新访问零答案问题"""
        print("开始零答案问题更新模式...")
        start_time = datetime.now()

        question_ids = self.get_zero_answer_questions()
        total_questions = len(question_ids)

        questions_updated = 0
        answers_added = 0
        acceptances_updated = 0

        print(f"需要检查 {total_questions} 个零答案问题...")

        for i, question_id in enumerate(question_ids, 1):
            if i % 20 == 0:
                print(f"进度: {i}/{total_questions} ({i/total_questions:.1%})")

            has_updates, latest_question, answers = self.check_question_updates(question_id)

            if has_updates and answers:
                if self.update_question_data(latest_question, answers):
                    questions_updated += 1
                    print(f"更新问题 #{question_id} (新增答案: {len(answers)})")

                    # 检查采纳情况
                    for answer in answers:
                        if answer.is_accepted:
                            acceptances_updated += 1
                    answers_added += len(answers)

            time.sleep(self.config.get('request_delay', 1.0))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        record = UpdateRecord(
            update_id=self.update_id,
            update_time=end_time.isoformat(),
            update_mode="zero_answer_update",
            questions_updated=questions_updated,
            answers_added=answers_added,
            acceptances_updated=acceptances_updated,
            questions_processed=total_questions,
            duration_seconds=duration,
            details=f"零答案问题更新 {total_questions} 个问题"
        )

        return record

    def run_no_accepted_update(self) -> UpdateRecord:
        """模式4: 重新访问有答案但无采纳的问题"""
        print("开始无采纳答案问题更新模式...")
        start_time = datetime.now()

        question_ids = self.get_questions_without_accepted_answer()
        total_questions = len(question_ids)

        questions_updated = 0
        answers_added = 0
        acceptances_updated = 0

        print(f"需要检查 {total_questions} 个有答案但无采纳的问题...")

        for i, question_id in enumerate(question_ids, 1):
            if i % 20 == 0:
                print(f"进度: {i}/{total_questions} ({i/total_questions:.1%})")

            has_updates, latest_question, answers = self.check_question_updates(question_id)

            if has_updates:
                # 检查是否有新的采纳答案
                has_new_acceptance = any(answer.is_accepted for answer in answers) if answers else False

                if self.update_question_data(latest_question, answers):
                    questions_updated += 1
                    if has_new_acceptance:
                        print(f"更新问题 #{question_id} (新增采纳答案!)")
                        acceptances_updated += 1
                    else:
                        print(f"更新问题 #{question_id} (答案更新)")

                    answers_added += len(answers)

            time.sleep(self.config.get('request_delay', 1.0))

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        record = UpdateRecord(
            update_id=self.update_id,
            update_time=end_time.isoformat(),
            update_mode="no_accepted_update",
            questions_updated=questions_updated,
            answers_added=answers_added,
            acceptances_updated=acceptances_updated,
            questions_processed=total_questions,
            duration_seconds=duration,
            details=f"无采纳答案问题更新 {total_questions} 个问题"
        )

        return record

    def execute_update(self, mode: str, backup_first: bool = True) -> bool:
        """执行更新"""
        print(f"执行数据更新模式: {mode}")

        if backup_first:
            print("正在备份数据到历史数据库...")
            try:
                self.history_manager.archive_current_data(self.main_db_path, self.update_id)
            except Exception as e:
                print(f"备份失败: {e}")
                return False

        # 执行更新
        if mode == "full":
            record = self.run_full_update()
        elif mode == "unanswered":
            record = self.run_unanswered_update()
        elif mode == "zero_answer":
            record = self.run_zero_answer_update()
        elif mode == "no_accepted":
            record = self.run_no_accepted_update()
        else:
            print(f"未知的更新模式: {mode}")
            return False

        # 保存更新记录
        self.history_manager.save_update_record(record)

        # 输出结果
        print("\n" + "="*50)
        print("更新完成")
        print("="*50)
        print(f"更新ID: {record.update_id}")
        print(f"更新模式: {record.update_mode}")
        print(f"处理问题数: {record.questions_processed}")
        print(f"更新问题数: {record.questions_updated}")
        print(f"新增答案数: {record.answers_added}")
        print(f"新增采纳数: {record.acceptances_updated}")
        print(f"耗时: {record.duration_seconds:.2f}秒")
        print(f"详情: {record.details}")
        print("="*50)

        return True

    def show_update_history(self):
        """显示更新历史"""
        stats = self.history_manager.get_history_stats()

        print("\n" + "="*50)
        print("历史数据更新记录")
        print("="*50)
        print(f"总更新次数: {stats['update_count']}")
        print(f"历史问题总数: {stats['total_questions']}")
        print(f"历史答案总数: {stats['total_answers']}")

        if stats['recent_updates']:
            print("\n最近更新记录:")
            for update in stats['recent_updates']:
                print(f"  {update['update_time']} [{update['update_mode']}] "
                      f"更新问题: {update['questions_updated']}, "
                      f"新增答案: {update['answers_added']}, "
                      f"新增采纳: {update['acceptances_updated']}")

        print("="*50)

def main():
    parser = argparse.ArgumentParser(description='Math Stack Exchange 数据更新器')
    parser.add_argument('mode',
                       choices=['full', 'unanswered', 'zero_answer', 'no_accepted', 'history'],
                       help='更新模式或查看历史')
    parser.add_argument('--main-db', default='math_se_data/math_se_questions.db',
                       help='主数据库路径')
    parser.add_argument('--history-db', default='math_se_data/history.db',
                       help='历史数据库路径')
    parser.add_argument('--config', default='crawler_config.json',
                       help='爬虫配置文件')
    parser.add_argument('--no-backup', action='store_true',
                       help='跳过数据备份')

    args = parser.parse_args()

    try:
        if args.mode == 'history':
            # 仅显示历史记录
            updater = DataUpdater(args.main_db, args.history_db)
            updater.show_update_history()
            return

        # 创建数据更新器
        updater = DataUpdater(args.main_db, args.history_db)

        # 检查主数据库是否存在
        if not os.path.exists(args.main_db):
            print(f"错误: 主数据库不存在: {args.main_db}")
            return

        # 执行更新
        success = updater.execute_update(args.mode, not args.no_backup)

        if success:
            print("更新任务完成")
        else:
            print("更新任务失败")

    except KeyboardInterrupt:
        print("\n更新任务被用户中断")
    except Exception as e:
        print(f"更新任务出错: {e}")

if __name__ == '__main__':
    main()