"""
爬虫运行脚本
支持后台运行和守护进程模式
"""

import os
import sys
import time
import subprocess
import traceback
import signal
import json
from datetime import datetime, timedelta
import argparse
import threading
import schedule
from pathlib import Path

from math_se_crawler import MathSECrawler, CrawlerConfig, CrawlerState
from crawler_config import CrawlerConfig as Config

class CrawlerManager:
    """爬虫管理器"""

    def __init__(self, config_file: str = "crawler_config.json"):
        self.config_file = config_file
        self.config = Config(config_file)
        self.state = CrawlerState()
        self.crawler = None
        self.running = False
        self.schedule_thread = None

    def setup_environment(self):
        """设置运行环境"""
        # 创建输出目录
        output_dir = self.config.get('output_dir', 'math_se_data')
        Path(output_dir).mkdir(exist_ok=True)

        # 设置日志文件
        default_log_file_name = 'crawler.log'
        log_file = self.config.get('log_file', default_log_file_name)
        if not os.path.isabs(log_file):
            log_file = os.path.join(output_dir, log_file)
        if not os.path.exists(log_file):
            log_file = os.path.join(output_dir, default_log_file_name)

        self.config.set('log_file', log_file)

        # 设置数据库文件
        db_path = os.path.join(output_dir, 'math_se_questions.db')
        self.config.set('db_path', db_path)

        print(f"运行环境设置完成:")
        print(f"  输出目录: {output_dir}")
        print(f"  日志文件: {log_file}")
        print(f"  数据库文件: {db_path}")

    def run_once(self, mode: str = 'incremental', **kwargs):
        """运行一次爬取"""
        print(f"开始单次爬取，模式: {mode}")

        # 更新配置
        for key, value in kwargs.items():
            if value is not None:
                self.config.set(key, value)

        # 创建爬虫实例
        self.crawler = MathSECrawler(self.config, self.state)

        # 运行爬取
        try:
            result = self.crawler.run(mode)

            # 输出结果
            print(f"\n爬取完成，结果:")
            print(f"  状态: {result.get('status')}")
            print(f"  爬取问题数: {result.get('crawled_count', 0)}")
            print(f"  成功数: {result.get('success_count', 0)}")
            print(f"  耗时: {result.get('duration', 0):.2f}秒")

            if result.get('status') == 'success':
                db_stats = result.get('database_stats', {})
                print(f"  数据库总问题数: {db_stats.get('total_questions', 0)}")
                print(f"  数据库总答案数: {db_stats.get('total_answers', 0)}")

            return result

        except KeyboardInterrupt:
            print(f"\n用户中断爬取")
            if self.crawler:
                self.crawler.stop()
            return None

        except Exception as e:
            print(f"爬取异常: {e}")
            return {'status': 'error', 'error': str(e)}

    def run_daemon(self, interval_hours: int = 6, **kwargs):
        """守护进程模式运行"""
        print(f"开始守护进程模式，间隔: {interval_hours}小时")

        def run_scheduled():
            print(f"定时爬取开始: {datetime.now()}")
            result = self.run_once('incremental', **kwargs)
            print(f"定时爬取完成: {datetime.now()}")
            return result

        # 设置定时任务
        schedule.every(interval_hours).hours.do(run_scheduled)

        # 立即运行一次
        run_scheduled()

        self.running = True
        print("守护进程启动，按 Ctrl+C 停止")

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            print("\n用户停止守护进程")
            self.running = False
        finally:
            print("守护进程已停止")

    def run_background(self, mode: str = 'incremental', **kwargs):
        """后台运行模式"""
        print("启动后台爬取模式")

        # 创建启动脚本
        script_path = "crawler_background.py"
        with open(script_path, 'w') as f:
            f.write(f'''
import sys
sys.path.append('{os.path.dirname(os.path.abspath(__file__))}')

from math_se_crawler import MathSECrawler, CrawlerConfig, CrawlerState

# 配置
config = CrawlerConfig('{self.config_file}')
state = CrawlerState()

# 更新配置
config_data = {json.dumps(kwargs, indent=2)}
for key, value in config_data.items():
    if value is not None:
        config.set(key, value)

# 创建并运行爬虫
crawler = MathSECrawler(config, state)
result = crawler.run('{mode}')

# 输出结果到文件
with open('last_run_result.json', 'w') as f:
    json.dump(result, f, indent=2, default=str)
''')

        # 启动后台进程
        try:
            if os.name == 'nt':  # Windows
                process = subprocess.Popen([sys.executable, script_path],
                                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:  # Unix/Linux/Mac
                process = subprocess.Popen([sys.executable, script_path],
                                         start_new_session=True)

            print(f"后台爬虫已启动，PID: {process.pid}")
            print(f"使用 'kill {process.pid}' 停止进程")
            print(f"结果将保存在 'last_run_result.json'")

            return process

        except Exception as e:
            print(f"启动后台进程失败: {e}")
            return None

    def resume_crawl(self):
        """恢复上次中断的爬取"""
        print("恢复爬取...")

        resume_info = self.state.get_resume_info()
        print(f"上次状态: {resume_info}")

        if resume_info['status'] == 'running':
            print("检测到未完成的爬取，尝试恢复...")
            return self.run_once('incremental')
        elif resume_info['status'] == 'paused':
            print("检测到暂停的爬取，继续执行...")
            return self.run_once('incremental')
        else:
            print("没有需要恢复的爬取任务")
            return None

    def check_status(self):
        """检查爬虫状态"""
        resume_info = self.state.get_resume_info()
        stats = None

        try:
            from math_se_crawler import DataStorage
            storage = DataStorage()
            stats = storage.get_crawl_stats()
        except Exception as e:
            print(f"获取数据库统计失败: {e}")

        print("\n" + "="*50)
        print("爬虫状态报告")
        print("="*50)

        print(f"运行状态: {resume_info['status']}")
        print(f"最后页码: {resume_info['last_page']}")
        print(f"最后问题ID: {resume_info['last_question_id']}")
        print(f"总爬取问题数: {resume_info['total_questions']}")
        print(f"失败问题数: {resume_info['failed_count']}")
        print(f"最后爬取时间: {resume_info['last_crawl_time']}")

        if stats:
            print(f"\n数据库统计:")
            print(f"  总问题数: {stats['total_questions']}")
            print(f"  总答案数: {stats['total_answers']}")
            print(f"  最新问题时间: {stats['latest_question_date']}")

        print("="*50)

        return resume_info, stats

def main():
    parser = argparse.ArgumentParser(description='Math Stack Exchange爬虫管理器')
    parser.add_argument('action', choices=['run', 'daemon', 'background', 'resume', 'status'],
                       help='操作: run(单次), daemon(守护), background(后台), resume(恢复), status(状态)')
    parser.add_argument('--mode', choices=['incremental', 'history'], default='incremental',
                       help='爬取模式')
    parser.add_argument('--config', default='crawler_config.json',
                       help='配置文件路径')
    parser.add_argument('--interval', type=int, default=6,
                       help='守护进程模式间隔(小时)')
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

    # 创建管理器
    manager = CrawlerManager(args.config)
    manager.setup_environment()

    # 准备参数
    kwargs = {
        'max_pages_per_run': args.max_pages,
        'api_key': args.api_key,
        'tags': args.tags,
        'min_score': args.min_score,
        'exclude_closed': args.exclude_closed
    }

    try:
        if args.action == 'run':
            manager.run_once(args.mode, **kwargs)
        elif args.action == 'daemon':
            manager.run_daemon(args.interval, **kwargs)
        elif args.action == 'background':
            manager.run_background(args.mode, **kwargs)
        elif args.action == 'resume':
            manager.resume_crawl()
        elif args.action == 'status':
            manager.check_status()

    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"操作失败: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()