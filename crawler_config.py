"""
Math Stack Exchange爬虫配置文件
支持持久化运行，包括历史爬虫和增量爬虫
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class CrawlerConfig:
    """爬虫配置管理类"""

    def __init__(self, config_file: str = "crawler_config.json"):
        self.config_file = config_file
        self.default_config = {
            "base_url": "https://math.stackexchange.com",
            "api_base": "https://api.stackexchange.com/2.3",
            "output_dir": "math_se_data",
            "state_file": "crawler_state.json",
            "log_file": "crawler.log",
            "max_pages_per_run": 100,  # 每次运行最大爬取页数
            "request_delay": 1.0,  # 请求间隔秒数
            "max_retries": 3,  # 最大重试次数
            "timeout": 30,  # 请求超时时间
            "user_agent": "Mozilla/5.0 (compatible; MathSE-Crawler/1.0)",
            "api_key": None,  # Stack Exchange API Key (可选)
            "questions_per_page": 50,  # 每页问题数量
            "max_age_days": 30,  # 增量爬取的天数范围
            "tags": [],  # 特定标签过滤
            "min_score": 0,  # 最低分数过滤
            "exclude_closed": False,  # 是否排除已关闭问题
            "proxy": None,  # 代理设置
            "concurrent_requests": 5,  # 并发请求数
        }
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和加载的配置
                    config = self.default_config.copy()
                    config.update(loaded_config)
                    return config
            except Exception as e:
                print(f"配置文件加载失败，使用默认配置: {e}")
                return self.default_config.copy()
        else:
            self.save_config()
            return self.default_config.copy()

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"配置文件保存失败: {e}")

    def get(self, key: str, default=None):
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key: str, value):
        """设置配置项"""
        self.config[key] = value
        self.save_config()

    def update_from_args(self, args: Dict):
        """从命令行参数更新配置"""
        for key, value in args.items():
            if value is not None and key in self.config:
                self.set(key, value)

class CrawlerState:
    """爬虫状态管理类"""

    def __init__(self, state_file: str = "crawler_state.json"):
        self.state_file = state_file
        self.default_state = {
            "last_page": 0,  # 最后爬取的页码
            "last_question_id": 0,  # 最后爬取的问题ID
            "total_questions": 0,  # 总爬取问题数
            "last_crawl_time": None,  # 最后爬取时间
            "crawled_questions": set(),  # 已爬取问题ID集合
            "failed_questions": [],  # 失败的问题ID列表
            "current_run": 0,  # 当前运行次数
            "status": "idle",  # 状态: idle, running, paused, error
            "error_message": None,  # 错误信息
            "start_time": None,  # 当前运行开始时间
        }
        self.state = self.load_state()

    def load_state(self) -> Dict:
        """加载状态文件"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    # 处理特殊数据类型
                    if 'crawled_questions' in state:
                        state['crawled_questions'] = set(state['crawled_questions'])
                    return state
            except Exception as e:
                print(f"状态文件加载失败，使用默认状态: {e}")
                return self.default_state.copy()
        else:
            return self.default_state.copy()

    def save_state(self):
        """保存状态文件"""
        try:
            # 准备保存的数据（转换set为list）
            save_data = self.state.copy()
            if 'crawled_questions' in save_data:
                save_data['crawled_questions'] = list(save_data['crawled_questions'])

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"状态文件保存失败: {e}")

    def get(self, key: str, default=None):
        """获取状态项"""
        return self.state.get(key, default)

    def set(self, key: str, value):
        """设置状态项"""
        self.state[key] = value
        self.save_state()

    def add_crawled_question(self, question_id: int):
        """添加已爬取的问题ID"""
        self.state['crawled_questions'].add(question_id)
        self.state['total_questions'] = len(self.state['crawled_questions'])
        self.save_state()

    def is_question_crawled(self, question_id: int) -> bool:
        """检查问题是否已爬取"""
        return question_id in self.state['crawled_questions']

    def increment_page(self):
        """增加页码"""
        self.state['last_page'] += 1
        self.save_state()

    def set_status(self, status: str, error_message: str = None):
        """设置爬虫状态"""
        self.state['status'] = status
        if error_message:
            self.state['error_message'] = error_message
        self.save_state()

    def reset_for_new_run(self):
        """为新运行重置状态"""
        self.state['current_run'] += 1
        self.state['start_time'] = datetime.now().isoformat()
        self.state['status'] = 'running'
        self.state['error_message'] = None
        self.save_state()

    def get_resume_info(self) -> Dict:
        """获取恢复信息"""
        return {
            'last_page': self.state.get('last_page', 0),
            'last_question_id': self.state.get('last_question_id', 0),
            'total_questions': self.state.get('total_questions', 0),
            'last_crawl_time': self.state.get('last_crawl_time'),
            'status': self.state.get('status', 'idle'),
            'failed_count': len(self.state.get('failed_questions', []))
        }