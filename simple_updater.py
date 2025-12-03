"""
简化的Math Stack Exchange数据更新器
专门用于检测和更新新答案和采纳状态
"""

import sqlite3
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Set
import requests
import json

class SimpleDataUpdater:
    """简化的数据更新器"""

    def __init__(self, db_path: str = "math_se_data/math_se_questions.db",
                 history_db_path: str = "math_se_data/history.db"):
        self.db_path = db_path
        self.history_db_path = history_db_path
        self.api_base = "https://api.stackexchange.com/2.3"
        self.request_delay = 2.0  # 增加延迟避免API限制
        self.max_retries = 2

        # 初始化历史数据库
        self.init_history_db()

    def init_history_db(self):
        """初始化历史数据库"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        # 创建更新记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                update_time TEXT,
                questions_checked INTEGER,
                questions_updated INTEGER,
                answers_added INTEGER,
                acceptances_found INTEGER,
                details TEXT
            )
        ''')

        # 创建历史答案表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historical_answers (
                answer_id INTEGER,
                question_id INTEGER,
                score INTEGER,
                is_accepted BOOLEAN,
                creation_date TEXT,
                last_activity_date TEXT,
                owner_info TEXT,
                body_preview TEXT,
                update_time TEXT,
                update_type TEXT,
                PRIMARY KEY (answer_id, update_time)
            )
        ''')

        conn.commit()
        conn.close()

    def get_db_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def make_api_request(self, url: str, params: Dict = None) -> Dict:
        """安全的API请求"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                time.sleep(self.request_delay)
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.request_delay * (2 ** attempt))
                else:
                    print(f"API请求失败: {url} - {e}")
                    return {"items": [], "has_more": False}

    def get_question_ids(self, condition: str = "") -> List[int]:
        """获取问题ID列表"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        if condition:
            cursor.execute(f"SELECT question_id FROM questions WHERE {condition}")
        else:
            cursor.execute("SELECT question_id FROM questions")

        ids = [row['question_id'] for row in cursor.fetchall()]
        conn.close()
        return ids

    def get_current_question_data(self, question_id: int) -> Dict:
        """获取当前问题数据"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM questions WHERE question_id = ?", (question_id,))
        question_row = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM answers WHERE question_id = ?", (question_id,))
        answer_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM answers WHERE question_id = ? AND is_accepted = 1", (question_id,))
        accepted_count = cursor.fetchone()[0]

        conn.close()

        if not question_row:
            return {}

        return {
            'question_id': question_row['question_id'],
            'score': question_row['score'],
            'view_count': question_row['view_count'],
            'answer_count': question_row['answer_count'],
            'last_activity_date': question_row['last_activity_date'],
            'is_answered': bool(question_row['is_answered']),
            'accepted_answer_id': question_row['accepted_answer_id'],
            'current_answer_count': answer_count,
            'current_accepted_count': accepted_count
        }

    def check_question_updates(self, question_id: int) -> Tuple[bool, Dict]:
        """检查单个问题的更新"""
        # 获取当前数据
        current_data = self.get_current_question_data(question_id)
        if not current_data:
            return False, {}

        # 获取最新数据
        url = f"{self.api_base}/questions/{question_id}"
        params = {
            'site': 'math',
            'filter': 'withbody',
            'order': 'desc',
            'sort': 'activity'
        }

        response = self.make_api_request(url, params)
        if not response.get('items'):
            return False, {}

        latest_item = response['items'][0]

        # 获取答案数据
        answer_url = f"{self.api_base}/questions/{question_id}/answers"
        answer_params = {
            'site': 'math',
            'filter': 'withbody',
            'order': 'desc',
            'sort': 'activity'
        }

        answer_response = self.make_api_request(answer_url, answer_params)
        latest_answers = answer_response.get('items', [])

        # 检查是否有更新
        latest_data = {
            'score': latest_item.get('score', 0),
            'view_count': latest_item.get('view_count', 0),
            'answer_count': latest_item.get('answer_count', 0),
            'last_activity_date': latest_item.get('last_activity_date', ''),
            'is_answered': latest_item.get('is_answered', False),
            'accepted_answer_id': latest_item.get('accepted_answer_id'),
            'latest_answer_count': len(latest_answers),
            'latest_accepted_count': sum(1 for a in latest_answers if a.get('is_accepted', False))
        }

        has_updates = (
            current_data['score'] != latest_data['score'] or
            current_data['view_count'] != latest_data['view_count'] or
            current_data['answer_count'] != latest_data['answer_count'] or
            current_data['last_activity_date'] != latest_data['last_activity_date'] or
            current_data['current_answer_count'] != latest_data['latest_answer_count'] or
            current_data['current_accepted_count'] != latest_data['latest_accepted_count']
        )

        if has_updates:
            # 保存到历史数据库
            self.save_answer_history(question_id, latest_answers)

        return has_updates, {
            'question_id': question_id,
            'current': current_data,
            'latest': latest_data,
            'new_answers': latest_answers,
            'has_new_acceptance': latest_data['latest_accepted_count'] > current_data['current_accepted_count']
        }

    def save_answer_history(self, question_id: int, answers: List[Dict]):
        """保存答案历史"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        update_time = datetime.now().isoformat()

        for answer in answers:
            body_preview = answer.get('body', '')[:200] + "..." if len(answer.get('body', '')) > 200 else answer.get('body', '')
            body_preview = body_preview.replace('\n', ' ').replace('\r', '')

            cursor.execute('''
                INSERT OR IGNORE INTO historical_answers
                    (answer_id, question_id, score, is_accepted, creation_date,
                     last_activity_date, owner_info, body_preview, update_time, update_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'auto_check')
            ''', (
                answer['answer_id'], question_id, answer.get('score', 0),
                answer.get('is_accepted', False), answer.get('creation_date', ''),
                answer.get('last_activity_date', ''), json.dumps(answer.get('owner', {})),
                body_preview, update_time
            ))

        conn.commit()
        conn.close()

    def update_main_database(self, update_data: Dict) -> bool:
        """更新主数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            latest = update_data['latest']
            question_id = update_data['question_id']

            # 更新问题表
            cursor.execute('''
                UPDATE questions SET
                    score = ?, view_count = ?, answer_count = ?, last_activity_date = ?,
                    is_answered = ?, accepted_answer_id = ?
                WHERE question_id = ?
            ''', (
                latest['score'], latest['view_count'], latest['answer_count'],
                latest['last_activity_date'], latest['is_answered'], latest['accepted_answer_id'],
                question_id
            ))

            # 注意：不更新答案，因为要保持原有数据结构
            # 新答案会保存在历史数据库中

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"更新主数据库失败 {question_id}: {e}")
            return False

    def run_update(self, mode: str = "zero_answer") -> Dict:
        """运行数据更新"""
        print(f"开始 {mode} 数据更新模式...")
        start_time = datetime.now()

        # 获取要检查的问题ID
        if mode == "zero_answer":
            condition = "answer_count = 0"
            description = "零答案问题"
        elif mode == "unaccepted":
            condition = "(answer_count > 0) AND (accepted_answer_id IS NULL OR accepted_answer_id = 0)"
            description = "有答案但无采纳的问题"
        elif mode == "all":
            condition = ""
            description = "所有问题"
        else:
            condition = ""
            description = "全部问题"

        question_ids = self.get_question_ids(condition)
        total_questions = len(question_ids)

        print(f"需要检查 {total_questions} 个{description}...")

        questions_checked = 0
        questions_updated = 0
        answers_added = 0
        acceptances_found = 0

        for i, question_id in enumerate(question_ids, 1):
            if i % 50 == 0:
                print(f"进度: {i}/{total_questions} ({i/total_questions:.1%})")

            has_updates, update_data = self.check_question_updates(question_id)
            questions_checked += 1

            if has_updates:
                if self.update_main_database(update_data):
                    questions_updated += 1
                    new_answers = len(update_data['new_answers']) - update_data['current']['current_answer_count']
                    answers_added += max(0, new_answers)
                    if update_data['has_new_acceptance']:
                        acceptances_found += 1

                    print(f"更新问题 #{question_id}: 新增{max(0, new_answers)}答案, "
                          f"{'发现采纳' if update_data['has_new_acceptance'] else '无新采纳'}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 记录更新日志
        self.log_update({
            'questions_checked': questions_checked,
            'questions_updated': questions_updated,
            'answers_added': answers_added,
            'acceptances_found': acceptances_found,
            'duration': duration,
            'mode': mode
        })

        return {
            'questions_checked': questions_checked,
            'questions_updated': questions_updated,
            'answers_added': answers_added,
            'acceptances_found': acceptances_found,
            'duration_seconds': duration,
            'mode': mode
        }

    def log_update(self, update_stats: Dict):
        """记录更新日志"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO update_log
            (update_time, questions_checked, questions_updated, answers_added,
             acceptances_found, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            update_stats['questions_checked'],
            update_stats['questions_updated'],
            update_stats['answers_added'],
            update_stats['acceptances_found'],
            f"模式: {update_stats['mode']}, 耗时: {update_stats['duration_seconds']:.2f}秒"
        ))

        conn.commit()
        conn.close()

    def show_update_history(self, limit: int = 10):
        """显示更新历史"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM update_log
            ORDER BY update_time DESC
            LIMIT ?
        ''', (limit,))

        updates = cursor.fetchall()

        if not updates:
            print("暂无更新记录")
            conn.close()
            return

        print("\n" + "="*60)
        print("更新历史记录")
        print("="*60)

        for update in updates:
            print(f"时间: {update['update_time']}")
            print(f"检查问题数: {update['questions_checked']}")
            print(f"更新问题数: {update['questions_updated']}")
            print(f"新增答案数: {update['answers_added']}")
            print(f"发现采纳数: {update['acceptances_found']}")
            print(f"详情: {update['details']}")
            print("-" * 60)

        # 显示总统计
        cursor.execute('''
            SELECT
                COUNT(*) as total_updates,
                SUM(questions_checked) as total_checked,
                SUM(questions_updated) as total_updated,
                SUM(answers_added) as total_answers,
                SUM(acceptances_found) as total_acceptances
            FROM update_log
        ''')

        stats = cursor.fetchone()
        if stats['total_updates']:
            print("\n总计统计:")
            print(f"更新次数: {stats['total_updates']}")
            print(f"总检查问题: {stats['total_checked']}")
            print(f"总更新问题: {stats['total_updated']}")
            print(f"总新增答案: {stats['total_answers']}")
            print(f"总发现采纳: {stats['total_acceptances']}")

        conn.close()

def main():
    parser = argparse.ArgumentParser(description='简化的Math Stack Exchange数据更新器')
    parser.add_argument('mode',
                       choices=['zero_answer', 'unaccepted', 'all', 'history'],
                       help='更新模式')
    parser.add_argument('--db-path', default='math_se_data/math_se_questions.db',
                       help='主数据库路径')
    parser.add_argument('--history-db', default='math_se_data/history.db',
                       help='历史数据库路径')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='API请求间隔（秒）')

    args = parser.parse_args()

    try:
        updater = SimpleDataUpdater(args.db_path, args.history_db)
        updater.request_delay = args.delay

        if args.mode == 'history':
            updater.show_update_history()
        else:
            result = updater.run_update(args.mode)

            print("\n" + "="*60)
            print("更新完成")
            print("="*60)
            print(f"更新模式: {result['mode']}")
            print(f"检查问题数: {result['questions_checked']}")
            print(f"更新问题数: {result['questions_updated']}")
            print(f"新增答案数: {result['answers_added']}")
            print(f"发现采纳数: {result['acceptances_found']}")
            print(f"耗时: {result['duration_seconds']:.2f}秒")
            print("="*60)

    except KeyboardInterrupt:
        print("\n更新被用户中断")
    except Exception as e:
        print(f"更新出错: {e}")

if __name__ == '__main__':
    main()