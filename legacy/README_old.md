# Math Stack Exchange 爬虫

一个用于抓取Math Stack Exchange问答的Python爬虫，支持持久化运行、状态恢复、增量爬取等功能。

## 功能特性

- ✅ **持久化运行**: 支持长时间运行，意外关闭后可恢复状态
- ✅ **增量爬取**: 基于上次爬取位置继续抓取新内容
- ✅ **历史爬取**: 从最新内容开始完整爬取
- ✅ **状态管理**: 完整的爬取状态跟踪和恢复
- ✅ **数据去重**: 自动避免重复爬取相同问题
- ✅ **错误处理**: 完善的重试机制和错误恢复
- ✅ **多种运行模式**: 单次、守护进程、后台运行
- ✅ **数据存储**: SQLite数据库存储，便于查询和分析
- ✅ **配置灵活**: 支持多种配置参数和过滤条件

## 安装依赖

### 爬虫依赖
```bash
pip install -r requirements.txt
```

### 数据查看器依赖
```bash
pip install -r viewer_requirements.txt
```

### 一次性安装所有依赖
```bash
pip install requests beautifulsoup4 lxml python-dateutil tqdm schedule flask rich
```

## 快速开始

### 1. 单次运行

```bash
# 增量爬取（默认）
python run_crawler.py run

# 历史爬取
python run_crawler.py run --mode history

# 指定页数
python run_crawler.py run --max-pages 50

# 指定标签
python run_crawler.py run --tags calculus algebra

# 设置最低分数
python run_crawler.py run --min-score 5
```

### 2. 守护进程模式

```bash
# 每6小时自动运行一次
python run_crawler.py daemon --interval 6

# 每天运行一次（24小时间隔）
python run_crawler.py daemon --interval 24
```

### 3. 后台运行

```bash
# 后台运行一次
python run_crawler.py background --mode history
```

### 4. 状态管理

```bash
# 查看爬虫状态
python run_crawler.py status

# 恢复中断的爬取
python run_crawler.py resume
```

## 配置说明

### 配置文件 (crawler_config.json)

```json
{
  "base_url": "https://math.stackexchange.com",
  "api_base": "https://api.stackexchange.com/2.3",
  "output_dir": "math_se_data",
  "log_file": "crawler.log",
  "max_pages_per_run": 100,
  "request_delay": 1.0,
  "max_retries": 3,
  "timeout": 30,
  "user_agent": "Mozilla/5.0 (compatible; MathSE-Crawler/1.0)",
  "api_key": null,
  "questions_per_page": 50,
  "max_age_days": 30,
  "tags": [],
  "min_score": 0,
  "exclude_closed": false,
  "proxy": null,
  "concurrent_requests": 5
}
```

### 主要参数说明

- `max_pages_per_run`: 每次运行最大爬取页数
- `request_delay`: 请求间隔（秒），避免频率过高
- `max_retries`: 请求失败最大重试次数
- `api_key`: Stack Exchange API Key（可选，提高请求限制）
- `questions_per_page`: 每页问题数量（最大100）
- `max_age_days`: 增量爬取的时间范围（天）
- `tags`: 指定爬取的标签列表
- `min_score`: 最低问题分数过滤
- `exclude_closed`: 是否排除已关闭的问题

## API Key 获取

为了获得更高的API请求限制，建议申请Stack Exchange API Key：

1. 访问 [Stack Apps](https://stackapps.com/apps/oauth/register)
2. 注册新应用
3. 获取API Key
4. 在配置文件中设置或在命令行使用 `--api-key` 参数

## 数据结构

### 问题表 (questions)

| 字段 | 类型 | 说明 |
|------|------|------|
| question_id | INTEGER | 问题ID（主键） |
| title | TEXT | 问题标题 |
| body | TEXT | 问题内容 |
| tags | TEXT | 标签（JSON格式） |
| score | INTEGER | 问题分数 |
| view_count | INTEGER | 浏览次数 |
| answer_count | INTEGER | 答案数量 |
| creation_date | TEXT | 创建时间 |
| last_activity_date | TEXT | 最后活动时间 |
| owner | TEXT | 作者信息（JSON格式） |
| link | TEXT | 问题链接 |
| is_answered | BOOLEAN | 是否有答案 |
| accepted_answer_id | INTEGER | 采纳答案ID |

### 答案表 (answers)

| 字段 | 类型 | 说明 |
|------|------|------|
| answer_id | INTEGER | 答案ID（主键） |
| question_id | INTEGER | 关联的问题ID |
| body | TEXT | 答案内容 |
| score | INTEGER | 答案分数 |
| creation_date | TEXT | 创建时间 |
| last_activity_date | TEXT | 最后活动时间 |
| owner | TEXT | 作者信息（JSON格式） |
| is_accepted | BOOLEAN | 是否被采纳 |

## 运行模式对比

| 模式 | 适用场景 | 特点 |
|------|----------|------|
| 单次运行 | 临时爬取、测试 | 简单直接，完成后退出 |
| 守护进程 | 长期稳定运行 | 定时自动运行，持续更新 |
| 后台运行 | 无界面环境 | 进程后台运行，输出到文件 |

## 状态恢复

爬虫支持自动状态恢复：

- **断点续传**: 意外关闭后可从上次位置继续
- **失败重试**: 失败的问题会记录，下次可重试
- **状态持久化**: 爬取进度实时保存到文件

## 日志和监控

- **日志文件**: `math_se_data/crawler.log`
- **状态文件**: `crawler_state.json`
- **数据库**: `math_se_data/math_se_questions.db`

## 示例用法

```bash
# 基础增量爬取
python run_crawler.py run

# 爬取微积分相关问题
python run_crawler.py run --tags calculus --min-score 10

# 完整历史爬取
python run_crawler.py run --mode history --max-pages 1000

# 守护进程模式，每12小时运行一次
python run_crawler.py daemon --interval 12 --tags linear-algebra

# 恢复中断的爬取
python run_crawler.py resume

# 查看当前状态
python run_crawler.py status
```

## 注意事项

1. **API限制**: Stack Exchange API有请求频率限制，建议配置合理的请求间隔
2. **版权遵守**: Math Stack Exchange内容采用CC BY-SA许可证，请遵守相关条款
3. **存储空间**: 大量爬取会占用较多存储空间，注意磁盘容量
4. **网络稳定性**: 长时间运行需要稳定的网络连接

## 故障排除

### 常见问题

1. **请求频繁被拒绝**
   - 增加请求间隔时间
   - 申请API Key
   - 减少并发请求数

2. **爬虫中断无法恢复**
   - 检查状态文件是否损坏
   - 重新初始化爬取状态

3. **数据库错误**
   - 检查数据库文件权限
   - 确保SQLite库正常工作

4. **内存占用过高**
   - 减少批处理大小
   - 增加垃圾回收频率

## 📊 数据查看器

本项目包含一个功能强大的数据查看器，用于浏览和搜索爬取的Math Stack Exchange题目和答案。

### 安装数据查看器依赖

```bash
pip install -r viewer_requirements.txt
```

主要依赖：
- `flask` - Web界面支持
- `rich` - 美化命令行界面

### 🖥️ 命令行界面 (CLI)

#### 交互式模式（推荐）
```bash
python data_viewer.py cli
```

启动后会显示可用命令：
- `id <问题ID>` - 查看指定ID的问题
- `index <索引>` - 查看指定索引的问题 (0-based)
- `random` - 随机问题
- `search <关键词>` - 搜索问题
- `tags <标签>` - 按标签查看问题
- `top <数量>` - 查看热门问题
- `stats` - 显示统计信息
- `quit` - 退出

#### 直接操作模式
```bash
# 查看数据库统计信息
python data_viewer.py cli --stats

# 查看特定问题
python data_viewer.py cli --id 5112040

# 查看索引问题
python data_viewer.py cli --index 10

# 随机问题
python data_viewer.py cli --random

# 搜索问题
python data_viewer.py cli --search "calculus"

# 按标签查看
python data_viewer.py cli --tags calculus algebra

# 查看热门问题
python data_viewer.py cli --top 20
```

### 🌐 Web界面

启动Web服务器：
```bash
# 默认配置 (http://localhost:5000)
python data_viewer.py web

# 自定义主机和端口
python data_viewer.py web --host 0.0.0.0 --port 8080

# 调试模式
python data_viewer.py web --debug
```

Web界面功能：
- **首页**: 显示数据库统计和热门问题
- **随机问题**: 点击"随机问题"按钮
- **搜索**: 全文搜索功能
- **问题详情**: 完整的问题和答案展示
- **API接口**: `/api/stats`, `/api/question/<id>`

### 📈 数据查看器功能特性

- ✅ **双模式界面**: 支持命令行和Web界面
- ✅ **随机展示**: 随机显示数学问题
- ✅ **编号跳转**: 通过问题ID或索引快速定位
- ✅ **全文搜索**: 支持标题、内容、标签搜索
- ✅ **数据统计**: 完整的数据库统计信息
- ✅ **标签过滤**: 按特定数学主题筛选问题
- ✅ **多种排序**: 按分数、浏览量、时间等排序
- ✅ **美观界面**: Rich库增强的命令行体验
- ✅ **响应式设计**: Web界面支持移动设备

### 💡 数据查看器使用示例

#### 1. 查看数据库概览
```bash
python data_viewer.py cli --stats
```

输出示例：
```
数据库统计信息
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ 指标           ┃ 数值       ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 总问题数       │ 50         │
│ 总答案数       │ 38         │
│ 有答案的问题数 │ 17         │
│ 平均分数       │ 1.64       │
│ 最高分数       │ 13         │
│ 最低分数       │ -5         │
│ 唯一标签数     │ 96         │
└────────────────┴────────────┘
```

#### 2. 浏览特定问题
```bash
python data_viewer.py cli --id 5112040
```

#### 3. 搜索相关问题
```bash
python data_viewer.py cli --search "calculus"
```

#### 4. 按数学主题浏览
```bash
python data_viewer.py cli --tags integration limits
```

#### 5. Web界面浏览
访问 http://localhost:5000 体验完整的Web界面。

### 📚 完整工作流程

```bash
# 1. 运行爬虫获取数据
python run_crawler.py run --max-pages 50

# 2. 查看爬取状态
python run_crawler.py status

# 3. 启动Web数据查看器
python data_viewer.py web

# 4. 或者使用命令行界面
python data_viewer.py cli --stats
python data_viewer.py cli --search "linear-algebra"
```

## 🔄 数据更新器

项目包含智能数据更新器，支持增量更新新答案和采纳状态，同时保留历史数据。

### 更新模式

```bash
# 零答案问题更新（最常用）
python simple_updater.py zero_answer

# 有答案但无采纳的问题更新
python simple_updater.py no_accepted

# 未回答问题更新
python simple_updater.py unanswered

# 全量更新（检查所有问题）
python simple_updater.py all

# 查看更新历史
python simple_updater.py history
```

### 更新器特性

- ✅ **智能检测** - 检测答案数量、采纳状态、分数、浏览量等变化
- ✅ **数据存档** - 每次更新前自动存档当前数据到历史库
- ✅ **历史记录** - 详细记录每次更新的统计信息和变化
- ✅ **安全保护** - 支持断点续传、错误恢复、API限制避免
- ✅ **性能优化** - 可配置延迟、条件筛选、进度显示

### 数据库结构

**主数据库** (`math_se_questions.db`):
- `questions` - 当前最新问题数据
- `answers` - 当前最新答案数据

**历史数据库** (`history.db`):
- `questions` - 历史问题数据（带update_id）
- `answers` - 历史答案数据（带update_id）
- `update_records` - 更新统计记录
- `historical_answers` - 被替换的答案详情

### 持久化策略

- 🔄 **增量更新** - 只检查需要更新的问题
- 💾 **数据保留** - 所有被替换的内容存入历史库
- 📊 **统计汇总** - 跟踪问题和答案的变化趋势
- 🗃️ **体积控制** - 压缩存储，可配置清理策略

### 使用示例

```bash
# 基础更新
python simple_updater.py zero_answer --delay 3.0

# 自定义路径
python simple_updater.py zero_answer --db-path custom.db --history-db history.db

# 查看更新历史
python simple_updater.py history --limit 10
```

### 监控和统计

```bash
# 查看当前数据库统计
python data_viewer.py cli --stats

# 查看更新历史
python simple_updater.py history

# 查看特定问题
python data_viewer.py cli --id 5111927
```

## 🚀 完整工作流程

```bash
# 1. 初始爬取数据
python run_crawler.py run --mode history --max-pages 20

# 2. 查看数据概览
python data_viewer.py cli --stats

# 3. 定期增量更新
python simple_updater.py zero_answer

# 4. 数据分析和浏览
python data_viewer.py web

# 5. 查看更新历史
python simple_updater.py history
```

## 扩展开发

项目采用模块化设计，可以轻松扩展：

- **新增数据源**: 修改爬虫类，添加新的数据源支持
- **自定义过滤器**: 在数据清洗阶段添加过滤逻辑
- **数据分析**: 基于SQLite数据进行进一步分析
- **数据查看器**: 扩展查看器的展示功能和界面
- **Web界面**: 开发Web管理界面监控爬取状态
- **更新策略**: 自定义数据更新逻辑和检测规则

## 许可证

本项目基于MIT许可证开源。

## 贡献

欢迎提交Issue和Pull Request来改进项目。