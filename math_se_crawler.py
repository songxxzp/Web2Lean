"""
Math Stack Exchange爬虫主程序
支持持久化运行、状态恢复、增量爬取
"""

import requests
import time
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import sys
from dataclasses import dataclass
import re

from crawler_config import CrawlerConfig, CrawlerState

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

class DataStorage:
    """数据存储管理类"""

    def __init__(self, db_path: str = "math_se_questions.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建问题表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                tags TEXT,
                score INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                answer_count INTEGER DEFAULT 0,
                creation_date TEXT,
                last_activity_date TEXT,
                owner TEXT,
                link TEXT,
                is_answered BOOLEAN DEFAULT FALSE,
                accepted_answer_id INTEGER,
                crawled_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建答案表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS answers (
                answer_id INTEGER PRIMARY KEY,
                question_id INTEGER,
                body TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                creation_date TEXT,
                last_activity_date TEXT,
                owner TEXT,
                is_accepted BOOLEAN DEFAULT FALSE,
                crawled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions (question_id)
            )
        ''')

        # 创建爬虫日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crawl_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                start_time TEXT,
                end_time TEXT,
                questions_crawled INTEGER DEFAULT 0,
                answers_crawled INTEGER DEFAULT 0,
                status TEXT,
                error_message TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def save_question(self, question: Question) -> bool:
        """保存问题到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO questions
                (question_id, title, body, tags, score, view_count, answer_count,
                 creation_date, last_activity_date, owner, link, is_answered, accepted_answer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                question.question_id,
                question.title,
                question.body,
                json.dumps(question.tags),
                question.score,
                question.view_count,
                question.answer_count,
                question.creation_date,
                question.last_activity_date,
                json.dumps(question.owner),
                question.link,
                question.is_answered,
                question.accepted_answer_id
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"保存问题失败: {e}")
            return False

    def save_answer(self, answer: Answer) -> bool:
        """保存答案到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO answers
                (answer_id, question_id, body, score, creation_date, last_activity_date,
                 owner, is_accepted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                answer.answer_id,
                answer.question_id,
                answer.body,
                answer.score,
                answer.creation_date,
                answer.last_activity_date,
                json.dumps(answer.owner),
                answer.is_accepted
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"保存答案失败: {e}")
            return False

    def question_exists(self, question_id: int) -> bool:
        """检查问题是否已存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM questions WHERE question_id = ?", (question_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_crawl_stats(self) -> Dict:
        """获取爬取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM questions")
        questions_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM answers")
        answers_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT creation_date FROM questions
            ORDER BY creation_date DESC LIMIT 1
        """)
        latest_question = cursor.fetchone()

        conn.close()

        return {
            'total_questions': questions_count,
            'total_answers': answers_count,
            'latest_question_date': latest_question[0] if latest_question else None
        }

class MathSECrawler:
    """Math Stack Exchange爬虫主类"""

    def __init__(self, config: CrawlerConfig = None, state: CrawlerState = None):
        self.config = config or CrawlerConfig()
        self.state = state or CrawlerState()
        self.storage = DataStorage(self.config.get('db_path', 'math_se_questions.db'))
        self.session = requests.Session()
        self.running = False
        self.run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 设置会话参数
        self.session.headers.update({
            'User-Agent': self.config.get('user_agent'),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })

        # 设置日志
        self.setup_logging()

        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.get('log_file', 'crawler.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def signal_handler(self, signum, frame):
        """信号处理器，用于优雅关闭"""
        self.logger.info(f"收到信号 {signum}，准备关闭爬虫...")
        self.running = False
        self.state.set_status('paused', f'用户中断 (信号 {signum})')

    def make_request(self, url: str, params: Dict = None, max_retries: int = None) -> Optional[Dict]:
        """发送HTTP请求，支持重试机制"""
        max_retries = max_retries or self.config.get('max_retries', 3)
        timeout = self.config.get('timeout', 30)
        delay = self.config.get('request_delay', 1.0)

        for attempt in range(max_retries):
            try:
                self.logger.debug(f"请求 URL: {url} (尝试 {attempt + 1}/{max_retries})")
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()

                # 请求间隔
                time.sleep(delay)

                return response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (2 ** attempt))  # 指数退避
                else:
                    self.logger.error(f"请求最终失败: {url}")
                    return None

    def fetch_questions_page(self, page: int = 1, pagesize: int = 50) -> List[Question]:
        """获取问题列表页面"""
        url = f"{self.config.get('api_base')}/questions"
        params = {
            'site': 'math',
            'page': page,
            'pagesize': pagesize,
            'order': 'desc',
            'sort': 'activity',
            'filter': 'withbody'
        }

        # 添加API Key（如果有）
        api_key = self.config.get('api_key')
        if api_key:
            params['key'] = api_key

        # 添加标签过滤
        tags = self.config.get('tags', [])
        if tags:
            params['tagged'] = ';'.join(tags)

        # 添加最小分数过滤
        min_score = self.config.get('min_score', 0)
        if min_score > 0:
            params['min'] = min_score

        # 增量爬取时间范围
        max_age_days = self.config.get('max_age_days', 30)
        if max_age_days > 0:
            since_date = datetime.now() - timedelta(days=max_age_days)
            params['fromdate'] = int(since_date.timestamp())

        response_data = self.make_request(url, params)
        if not response_data or 'items' not in response_data:
            return []

        questions = []
        for item in response_data['items']:
            try:
                question = Question(
                    question_id=item['question_id'],
                    title=self.clean_html(item['title']),
                    body=self.clean_html(item.get('body', '')),
                    tags=item.get('tags', []),
                    score=item.get('score', 0),
                    view_count=item.get('view_count', 0),
                    answer_count=item.get('answer_count', 0),
                    creation_date=item.get('creation_date', ''),
                    last_activity_date=item.get('last_activity_date', ''),
                    owner=item.get('owner', {}),
                    link=item.get('link', ''),
                    is_answered=item.get('is_answered', False),
                    accepted_answer_id=item.get('accepted_answer_id')
                )

                # 检查是否排除已关闭的问题
                if self.config.get('exclude_closed', False) and item.get('closed_date'):
                    continue

                questions.append(question)

            except Exception as e:
                self.logger.error(f"解析问题数据失败: {e}")
                continue

        return questions

    def fetch_answers_for_question(self, question_id: int) -> List[Answer]:
        """获取问题的所有答案"""
        url = f"{self.config.get('api_base')}/questions/{question_id}/answers"
        params = {
            'site': 'math',
            'order': 'desc',
            'sort': 'votes',
            'filter': 'withbody'
        }

        response_data = self.make_request(url, params)
        if not response_data or 'items' not in response_data:
            return []

        answers = []
        for item in response_data['items']:
            try:
                answer = Answer(
                    answer_id=item['answer_id'],
                    question_id=question_id,
                    body=self.clean_html(item.get('body', '')),
                    score=item.get('score', 0),
                    creation_date=item.get('creation_date', ''),
                    last_activity_date=item.get('last_activity_date', ''),
                    owner=item.get('owner', {}),
                    is_accepted=item.get('is_accepted', False)
                )
                answers.append(answer)

            except Exception as e:
                self.logger.error(f"解析答案数据失败: {e}")
                continue

        return answers

    def clean_html(self, text: str) -> str:
        """清理HTML标签，保留数学公式"""
        if not text:
            return ""

        # 替换常见的HTML标签
        text = re.sub(r'<[^>]+>', '', text)  # 移除HTML标签
        text = re.sub(r'&nbsp;', ' ', text)  # 空格实体
        text = re.sub(r'&amp;', '&', text)   # &实体
        text = re.sub(r'&lt;', '<', text)    # <实体
        text = re.sub(r'&gt;', '>', text)    # >实体
        text = re.sub(r'&quot;', '"', text)  # "实体
        text = re.sub(r'&#39;', "'", text)    # '实体

        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    def crawl_question_with_answers(self, question: Question) -> bool:
        """爬取问题及其答案"""
        if self.storage.question_exists(question.question_id):
            self.logger.debug(f"问题已存在，跳过: {question.question_id}")
            return True

        try:
            # 保存问题
            if not self.storage.save_question(question):
                self.logger.error(f"保存问题失败: {question.question_id}")
                return False

            # 爬取答案
            answers = self.fetch_answers_for_question(question.question_id)
            for answer in answers:
                self.storage.save_answer(answer)

            # 更新状态
            self.state.add_crawled_question(question.question_id)
            self.state.set('last_question_id', question.question_id)

            self.logger.info(f"成功爬取问题 {question.question_id} 及 {len(answers)} 个答案")
            return True

        except Exception as e:
            self.logger.error(f"爬取问题失败 {question.question_id}: {e}")
            # 添加到失败列表
            failed_questions = self.state.get('failed_questions', [])
            failed_questions.append(question.question_id)
            self.state.set('failed_questions', failed_questions)
            return False

    def crawl_incremental(self) -> Dict:
        """增量爬取模式"""
        self.logger.info("开始增量爬取...")

        start_page = self.state.get('last_page', 0) + 1
        max_pages = self.config.get('max_pages_per_run', 100)
        pagesize = self.config.get('questions_per_page', 50)

        crawled_count = 0
        success_count = 0

        for page in range(start_page, start_page + max_pages):
            if not self.running:
                self.logger.info("爬虫被中断")
                break

            self.logger.info(f"爬取第 {page} 页...")

            questions = self.fetch_questions_page(page, pagesize)
            if not questions:
                self.logger.info(f"第 {page} 页没有数据，结束爬取")
                break

            for question in questions:
                if not self.running:
                    break

                crawled_count += 1
                if self.crawl_question_with_answers(question):
                    success_count += 1

            # 更新页码状态
            self.state.set('last_page', page)

            # 检查是否还有更多数据
            if len(questions) < pagesize:
                self.logger.info("已到达数据末尾")
                break

        return {
            'crawled_count': crawled_count,
            'success_count': success_count,
            'pages_processed': page - start_page + 1
        }

    def crawl_history(self, max_pages: int = None) -> Dict:
        """历史爬取模式 - 从最新开始"""
        self.logger.info("开始历史爬取...")

        max_pages = max_pages or self.config.get('max_pages_per_run', 100)
        pagesize = self.config.get('questions_per_page', 50)

        crawled_count = 0
        success_count = 0

        for page in range(1, max_pages + 1):
            if not self.running:
                self.logger.info("爬虫被中断")
                break

            self.logger.info(f"历史爬取第 {page} 页...")

            questions = self.fetch_questions_page(page, pagesize)
            if not questions:
                self.logger.info(f"第 {page} 页没有数据，结束爬取")
                break

            for question in questions:
                if not self.running:
                    break

                crawled_count += 1
                if self.crawl_question_with_answers(question):
                    success_count += 1

        return {
            'crawled_count': crawled_count,
            'success_count': success_count,
            'pages_processed': page - 1
        }

    def run(self, mode: str = 'incremental') -> Dict:
        """运行爬虫"""
        self.running = True
        self.state.reset_for_new_run()

        start_time = datetime.now()
        self.logger.info(f"开始爬取，模式: {mode}, 运行ID: {self.run_id}")

        try:
            if mode == 'incremental':
                result = self.crawl_incremental()
            elif mode == 'history':
                result = self.crawl_history()
            else:
                raise ValueError(f"不支持的爬取模式: {mode}")

            # 记录结束状态
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self.state.set_status('completed')
            self.logger.info(f"爬取完成，耗时: {duration:.2f}秒")

            # 获取统计信息
            stats = self.storage.get_crawl_stats()

            return {
                'status': 'success',
                'mode': mode,
                'run_id': self.run_id,
                'duration': duration,
                **result,
                'database_stats': stats,
                'state': self.state.get_resume_info()
            }

        except Exception as e:
            self.state.set_status('error', str(e))
            self.logger.error(f"爬取失败: {e}")
            return {
                'status': 'error',
                'mode': mode,
                'run_id': self.run_id,
                'error': str(e)
            }

    def stop(self):
        """停止爬虫"""
        self.running = False
        self.state.set_status('stopped', '用户手动停止')

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Math Stack Exchange爬虫')
    parser.add_argument('--mode', choices=['incremental', 'history'], default='incremental',
                       help='爬取模式: incremental(增量) 或 history(历史)')
    parser.add_argument('--config', default='crawler_config.json',
                       help='配置文件路径')
    parser.add_argument('--max-pages', type=int,
                       help='最大爬取页数')
    parser.add_argument('--api-key',
                       help='Stack Exchange API Key')
    parser.add_argument('--tags', nargs='*',
                       help='要爬取的标签')
    parser.add_argument('--min-score', type=int,
                       help='最低问题分数')
    parser.add_argument('--exclude-closed', action='store_true',
                       help='排除已关闭的问题')

    args = parser.parse_args()

    # 加载配置
    config = CrawlerConfig(args.config)

    # 从命令行参数更新配置
    config.update_from_args({
        'max_pages_per_run': args.max_pages,
        'api_key': args.api_key,
        'tags': args.tags,
        'min_score': args.min_score,
        'exclude_closed': args.exclude_closed
    })

    # 创建爬虫实例
    crawler = MathSECrawler(config)

    # 运行爬虫
    result = crawler.run(args.mode)

    # 输出结果
    print("\n" + "="*50)
    print("爬取结果:")
    print(f"状态: {result.get('status', 'unknown')}")
    print(f"模式: {result.get('mode', 'unknown')}")
    print(f"运行ID: {result.get('run_id', 'unknown')}")

    if result.get('status') == 'success':
        print(f"爬取问题数: {result.get('crawled_count', 0)}")
        print(f"成功数: {result.get('success_count', 0)}")
        print(f"处理页数: {result.get('pages_processed', 0)}")
        print(f"耗时: {result.get('duration', 0):.2f}秒")

        db_stats = result.get('database_stats', {})
        print(f"数据库总问题数: {db_stats.get('total_questions', 0)}")
        print(f"数据库总答案数: {db_stats.get('total_answers', 0)}")
    else:
        print(f"错误: {result.get('error', 'Unknown error')}")

    print("="*50)

if __name__ == '__main__':
    main()