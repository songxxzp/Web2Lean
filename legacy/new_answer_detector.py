"""
新答案检测器
专门检测新答案和采纳状态，不更新历史数据
"""

import sqlite3
import time
import requests
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json

class NewAnswerDetector:
    """新答案检测器"""

    def __init__(self, db_path: str = "math_se_data/math_se_questions.db",
                 history_db_path: str = "math_se_data/new_answer_history.db"):
        self.db_path = db_path
        self.history_db_path = history_db_path
        self.api_base = "https://api.stackexchange.com/2.3"
        self.request_delay = 2.0  # 保守的请求延迟
        self.max_retries = 3
        self.timeout = 30

        # 初始化历史数据库
        self.init_history_db()

    def init_history_db(self):
        """初始化历史数据库"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        # 创建检测记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_answer_detection (
                detection_id TEXT PRIMARY KEY,
                question_id INTEGER,
                previous_answer_count INTEGER,
                new_answer_count INTEGER,
                new_acceptance BOOLEAN,
                detection_time TEXT,
                details TEXT
            )
        ''')

        # 创建新答案历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_answers (
                answer_id INTEGER PRIMARY KEY,
                question_id INTEGER,
                score INTEGER,
                creation_date TEXT,
                last_activity_date TEXT,
                owner_info TEXT,
                is_accepted BOOLEAN,
                first_seen_time TEXT,
                detection_id TEXT,
                FOREIGN KEY (detection_id) REFERENCES new_answer_detection(detection_id)
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_detection_questions ON new_answer_detection(question_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_detection_time ON new_answer_detection(detection_time)')

        conn.commit()
        conn.close()
        print(f"历史数据库初始化完成: {self.history_db_path}")

    def get_db_connection(self) -> sqlite3.Connection:
        """获取主数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def check_question_for_new_answers(self, question_id: int) -> Tuple[bool, List[Dict]]:
        """检查问题是否有新答案"""
        # 获取当前数据
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM questions WHERE question_id = ?", (question_id,))
        current_row = cursor.fetchone()
        if not current_row:
            conn.close()
            return False, []

        current_data = {
            'answer_count': current_row['answer_count'],
            'accepted_answer_id': current_row['accepted_answer_id'],
            'last_activity_date': current_row['last_activity_date'],
            'score': current_row['score']
        }

        # 获取最新数据
        url = f"{self.api_base}/questions/{question_id}/answers?site=math&order=desc&sort=activity&filter=withbody"
        params = {
            'site': 'math',
            'order': 'desc',
            'sort': 'activity',
            'filter': 'withbody'
        }

        response = self.make_api_request(url, params)
        if not response or 'items' not in response:
            conn.close()
            return False, []

        latest_answers = response['items']
        new_answer_count = len(latest_answers)
        new_acceptance = any(answer.get('is_accepted', False) for answer in latest_answers)
        new_activity_date = latest_answers[0].get('last_activity_date', '') if latest_answers else ''

        # 检查是否有变化
        has_changes = (
            current_data['answer_count'] != new_answer_count or
            current_data['accepted_answer_id'] != (latest_answers[0].get('answer_id') if latest_answers and latest_answers[0].get('is_accepted') else None) or
            current_data['last_activity_date'] != new_activity_date or
            len([a for a in latest_answers if a.get('owner', {}).get('display_name', 'Community')]) > 1  # 有来自不同用户的答案
        )

        conn.close()

        if has_changes:
            # 记录检测
            self.save_detection_record(question_id, current_data, latest_answers)

        return has_changes, latest_answers

    def make_api_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """安全的API请求"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.request_delay * (2 ** attempt))
                else:
                    print(f"API请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                return None
            except Exception as e:
                print(f"API请求异常: {e}")
                return None

    def save_detection_record(self, question_id: int, current_data: Dict, new_answers: List[Dict]):
        """保存检测记录"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        detection_id = f"detection_{question_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 记录检测
        cursor.execute('''
            INSERT INTO new_answer_detection
                (detection_id, question_id, previous_answer_count, new_answer_count,
                 new_acceptance, detection_time, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
            detection_id,
            question_id,
            current_data['answer_count'],
            new_answer_count,
            new_acceptance,
            datetime.now().isoformat(),
            json.dumps({
                'new_answer_count': new_answer_count,
                'previous_answer_count': current_data['answer_count'],
                'new_answers_count': len(new_answers),
                'new_acceptance': new_acceptance,
                'new_answer_ids': [a['answer_id'] for a in new_answers],
                'has_new_acceptance': new_acceptance,
                'previous_accepted': current_data['accepted_answer_id'],
                'newly_accepted': [a['answer_id'] for a in new_answers if a.get('is_accepted', False)],
                'answer_sources': [a.get('owner', {}).get('display_name', 'Unknown') for a in new_answers]
            }, ensure_ascii=False)
        ))

        conn.commit()
        conn.close()

    def get_recent_detections(self, limit: int = 10) -> List[Dict]:
        """获取最近的检测记录"""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM new_answer_detection
            ORDER BY detection_time DESC
            LIMIT ?
        ''', (limit,))

        records = cursor.fetchall()
        conn.close()

        # 转换为字典
        result = []
        for row in records:
            record = dict(row)
            # 解析JSON字段
            try:
                details = json.loads(record['details']) if record['details'] else {}
            except:
                details = record['details']

            result.append({
                'detection_id': record['detection_id'],
                'question_id': record['question_id'],
                'previous_answer_count': record['previous_answer_count'],
                'new_answer_count': record['new_answer_count'],
                'new_acceptance': bool(record['new_acceptance']),
                'detection_time': record['detection_time'],
                'has_new_acceptances': details.get('has_new_acceptance', False),
                'details': details
            })

        return result

    def run_detection(self, question_ids: List[int], progress_callback=None) -> Dict:
        """运行新答案检测"""
        print(f"开始检查 {len(question_ids)} 个问题...")

        total_checked = 0
        total_with_new_answers = 0
        total_with_new_acceptances = 0
        total_new_answers = 0

        start_time = datetime.now()

        for i, question_id in enumerate(question_ids, 1):
            has_changes, new_answers = self.check_question_for_new_answers(question_id)

            total_checked += 1

            if has_changes:
                new_answer_count = len([a for a in new_answers if a.get('creation_date', '')]) - (len([a for a in new_answers if a.get('creation_date', '')] - len([a for a in new_answers if a.get('creation_date', '') and a.get('owner', {}).get('display_name', 'Community')])
                total_new_answers += new_answer_count

                if any(a.get('is_accepted', False) for a in new_answers):
                    total_with_new_acceptances += 1

            if progress_callback and i % 10 == 0:
                progress = i / len(question_ids)
                progress_callback(f"进度: {progress:.1%} - 检查到第 {i} 个问题")

            # 延迟以避免API限制
            if i % 10 == 0 and i != len(question_ids):
                time.sleep(self.request_delay * 2)  # 每10个问题后多延迟

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 统计
        avg_time = duration / len(question_ids) if question_ids else 0

        return {
            'total_checked': total_checked,
            'total_with_new_answers': total_with_new_answers,
            'total_with_new_acceptances': total_with_new_acceptances,
            'total_new_answers': total_new_answers,
            'duration_seconds': duration,
            'avg_time_per_question': avg_time,
            'questions_with_new_acceptances': [
                question_id for i, question_id in enumerate(question_ids, 1)
                if i < len(question_ids) and self.check_question_for_new_answers(question_id)[0]
                and any(a.get('is_accepted', False) for a in self.check_question_for_new_answers(question_id)[0])
            ]
            ]
        }

    def show_detection_summary(self):
        """显示检测摘要"""
        detections = self.get_recent_detections(limit=5)

        if not detections:
            print("暂无检测记录")
            return

        print("\n" + "="*60)
        print("新答案检测摘要")
        print("="*60)

        for i, detection in enumerate(detections, 1):
            details = json.loads(detection['details']) if detection['details'] else {}
            print(f"{i}. 问题 #{detection['question_id']} ({detection['detection_time']})")
            print(f"    原答案数: {detection['previous_answer_count']} → {detection['new_answer_count']}")
            if detection['new_acceptance']:
                print(f"    ✓ 发现新采纳: {details.get('newly_accepted', [])}")
            print(f"    📊 新答案来源: {set(details.get('answer_sources', []))}")

            new_answers = details.get('new_answers_count', 0)
            if new_answers > 0:
                avg_score = sum(a.get('score', 0) for a in self.make_api_request(f"{self.api_base}/questions/{detection['question_id']}/answers?site=math&filter=withbody&sort=votes").get('items', [])) / new_answers
                print(f"    📊 新答案平均分数: {avg_score:.1f}")

        print("="*60)

def main():
    parser = argparse.ArgumentParser(description='新答案检测器')
    parser.add_argument('question_ids', nargs='+', type=int,
                       help='要检查的问题ID列表')
    parser.add_argument('--db-path', default='math_se_data/math_se_questions.db',
                       help='主数据库路径')
    parser.add_argument('--history-db', default='math_se_data/new_answer_history.db',
                       help='历史数据库路径')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='请求延迟（秒）')
    parser.add_argument('--limit', type=int, default=20,
                       help='显示最近检测记录数量')
    parser.add_argument('--show-summary', action='store_true',
                       help='只显示检测摘要，不运行检测')

    args = parser.parse_args()

    try:
        detector = NewAnswerDetector(args.db_path, args.history_db_path)
        detector.request_delay = args.delay

        if args.show_summary:
            detector.show_detection_summary()
            return

        # 运行检测
        result = detector.run_detection(args.question_ids)

        print("\n" + "="*60)
        print("检测完成")
        print("="*60)

        # 显示结果
        print(f"总检查问题数: {result['total_checked']}")
        print(f"发现新答案的问题数: {result['total_with_new_answers']}")
        print(f"发现新采纳的问题数: {result['total_with_new_acceptances']}")
        print(f"总新增答案数: {result['total_new_answers']}")
        print(f"平均每个问题耗时: {result['avg_time_per_question']:.2f}秒")
        print(f"检测总耗时: {result['duration_seconds']:.2f}秒")

        # 显示有新采纳的问题
        if result['questions_with_new_acceptances']:
            print(f"\n有新采纳的问题 ({len(result['questions_with_new_acceptances'])}个):")
            for qid in result['questions_with_new_acceptances']:
                print(f"  问题 #{qid}")

    except KeyboardInterrupt:
        print("\n检测被用户中断")
    except Exception as e:
        print(f"检测出错: {e}")

if __name__ == '__main__':
    main()