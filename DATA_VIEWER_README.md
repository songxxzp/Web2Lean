# Math Stack Exchange 数据查看器

一个功能强大的数据查看器，用于浏览和搜索爬取的Math Stack Exchange题目和答案。

## 功能特性

- ✅ **双模式界面**: 支持命令行和Web界面
- ✅ **随机展示**: 随机显示数学问题
- ✅ **编号跳转**: 通过问题ID或索引快速定位
- ✅ **全文搜索**: 支持标题、内容、标签搜索
- ✅ **数据统计**: 完整的数据库统计信息
- ✅ **标签过滤**: 按特定标签查看问题
- ✅ **排序功能**: 按分数、浏览、时间等排序
- ✅ **美观界面**: Rich库增强的命令行体验

## 安装依赖

```bash
pip install -r viewer_requirements.txt
```

主要依赖：
- `flask` - Web界面支持
- `rich` - 美化命令行界面
- `requests` - HTTP请求（爬虫功能）

## 使用方法

### 命令行界面 (CLI)

#### 交互式模式
```bash
python data_viewer.py cli
```

启动后会显示可用的交互命令：
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
# 查看统计信息
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

# 热门问题
python data_viewer.py cli --top 20
```

### Web界面

```bash
# 启动Web服务器
python data_viewer.py web

# 自定义主机和端口
python data_viewer.py web --host 0.0.0.0 --port 8080

# 调试模式
python data_viewer.py web --debug
```

访问地址：http://localhost:5000

Web界面功能：
- 首页：显示统计信息和热门问题
- 随机问题：随机浏览数学问题
- 搜索：全文搜索功能
- 问题详情：完整的问题和答案展示
- 响应式设计：支持移动设备

## 数据库结构

### 问题表 (questions)
- `question_id` - 问题ID（主键）
- `title` - 问题标题
- `body` - 问题内容
- `tags` - 标签列表（JSON格式）
- `score` - 问题分数
- `view_count` - 浏览次数
- `answer_count` - 答案数量
- `creation_date` - 创建时间
- `last_activity_date` - 最后活动时间
- `owner` - 作者信息（JSON格式）
- `link` - 原始链接
- `is_answered` - 是否有答案
- `accepted_answer_id` - 采纳答案ID

### 答案表 (answers)
- `answer_id` - 答案ID（主键）
- `question_id` - 关联问题ID
- `body` - 答案内容
- `score` - 答案分数
- `creation_date` - 创建时间
- `last_activity_date` - 最后活动时间
- `owner` - 作者信息（JSON格式）
- `is_accepted` - 是否被采纳

## 使用示例

### 1. 查看数据库概览
```bash
python data_viewer.py cli --stats
```

输出示例：
```
数据库统计信息
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ 指标           ┃ 数值       ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 总问题数       │ 50         │
│ 总答案数       │ 38         │
│ 有答案的问题数 │ 17         │
│ 平均分数       │ 1.64       │
│ 最高分数       │ 13         │
│ 最低分数       │ -5         │
│ 唯一标签数     │ 96         │
└────────────────┴────────────┘
```

### 2. 浏览特定问题
```bash
python data_viewer.py cli --id 5112040
```

输出示例：
```
问题 #5112040: Probabilistic argument for 10 close points...
────────────────────────────────────────────────────────────
分数: 1 | 浏览: 26 | 答案: 0
标签: combinatorial-geometry, probabilistic-method
链接: https://math.stackexchange.com/questions/5112040

问题内容:
This problem has already been posted here many years ago...
```

### 3. 搜索相关问题
```bash
python data_viewer.py cli --search "calculus"
```

输出示例：
```
找到 7 个包含 'calculus' 的问题:
1. #5112069 $f(x)$ and $g(x)$ are increasing... (分数: 6, 答案: 1)
2. #5111911 On $\int_{0}^{\frac{\pi}{2}} \sin(x)^{-\sin(x)}$... (分数: 4, 答案: 1)
3. #5111919 Why is $y = \sin(\frac{y^2}{t} - k)$... (分数: 2, 答案: 1)
```

### 4. 按标签浏览
```bash
python data_viewer.py cli --tags calculus integration
```

### 5. Web界面浏览
启动Web服务器后，在浏览器中访问 http://localhost:5000

- **首页**：显示数据库概览和热门问题
- **随机问题**：点击"随机问题"按钮
- **搜索**：使用搜索框查找感兴趣的内容
- **问题详情**：点击任何问题查看完整内容和答案

## 高级功能

### 1. 数据统计分析
自动分析数据库内容，包括：
- 问题数量统计
- 答案分布情况
- 标签使用频率
- 分数分布情况
- 时间分布分析

### 2. 智能搜索
支持多种搜索模式：
- `all` - 搜索标题、内容和标签
- `title` - 仅搜索标题
- `body` - 仅搜索内容
- `tags` - 仅搜索标签

### 3. 多种排序
支持多种排序方式：
- `score` - 按分数排序（默认）
- `views` - 按浏览次数排序
- `answers` - 按答案数量排序
- `recent` - 按创建时间排序

### 4. API接口
Web界面提供JSON API：
- `/api/stats` - 获取统计信息
- `/api/question/<id>` - 获取问题数据

## 配置选项

可以通过命令行参数配置查看器：

```bash
python data_viewer.py --db /path/to/database.db \
    --host 0.0.0.0 \
    --port 8080 \
    --debug
```

参数说明：
- `--db` - 数据库文件路径
- `--host` - Web服务器主机地址
- `--port` - Web服务器端口
- `--debug` - 启用调试模式

## 故障排除

### 1. 数据库文件不存在
```
错误: FileNotFoundError: 数据库文件不存在: math_se_questions.db
```

**解决方案**：先运行爬虫获取数据
```bash
python math_se_crawler.py --max-pages 10
```

### 2. 依赖库缺失
```
错误: ModuleNotFoundError: No module named 'flask'
```

**解决方案**：安装依赖库
```bash
pip install -r viewer_requirements.txt
```

### 3. 权限问题
确保数据库文件有读取权限：
```bash
chmod 644 math_se_questions.db
```

### 4. 端口占用
如果端口被占用，更换端口：
```bash
python data_viewer.py web --port 8081
```

## 扩展开发

### 1. 添加新的数据展示格式
可以修改`render_question_rich`函数来自定义显示格式。

### 2. 增加搜索功能
在`DatabaseManager`类中添加新的搜索方法。

### 3. 自定义Web界面
修改WebDataViewer类中的模板来自定义Web界面。

### 4. 添加数据分析功能
利用Python的数据分析库（如pandas、matplotlib）进行深度分析。

## 性能优化

### 1. 数据库索引
```sql
CREATE INDEX idx_question_score ON questions(score);
CREATE INDEX idx_question_creation_date ON questions(creation_date);
CREATE INDEX idx_answer_question_id ON answers(question_id);
```

### 2. 分页查询
对于大量数据，实现分页查询以提高响应速度。

### 3. 缓存机制
实现查询结果缓存，减少数据库访问。

## 许可证

本项目基于MIT许可证开源。

## 贡献

欢迎提交Issue和Pull Request来改进数据查看器！