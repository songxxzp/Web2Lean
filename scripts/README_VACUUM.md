# 数据库清理脚本使用说明

## 脚本位置
```
/datadisk/Web2Lean/scripts/vacuum_database.sh
```

## 使用方法

### 运行清理脚本
```bash
cd /datadisk/Web2Lean
./scripts/vacuum_database.sh
```

或者直接使用完整路径：
```bash
/datadisk/Web2Lean/scripts/vacuum_database.sh
```

## 脚本功能

该脚本会：

1. **检查数据库状态**
   - 显示当前数据库大小
   - 显示各表的记录数
   - 检查碎片程度（空闲空间）

2. **确认提示**
   - 询问是否继续执行VACUUM

3. **创建备份**
   - 自动创建数据库备份（带时间戳）
   - 备份位置：`data/databases/web2lean.db.backup.YYYYMMDD_HHMMSS`

4. **执行VACUUM**
   - 清理数据库碎片
   - 回收删除数据占用的空间
   - 显示执行时间

5. **验证完整性**
   - 检查数据库完整性
   - 对比前后的记录数（确保数据未丢失）
   - 显示新的数据库大小

## 何时需要运行

建议在以下情况运行此脚本：

1. **大量删除数据后** - 例如使用"Delete All Data"或"Clear All"功能后
2. **定期维护** - 每月或每周运行一次（取决于数据变更频率）
3. **数据库文件异常大** - 如果发现数据库文件大小远超预期

## 示例输出

```
==========================================
  SQLite Database Vacuum Script
==========================================

Current database size: 423M

Record counts before vacuum:
  questions: 1487
  answers: 1812
  processing_status: 1486

Checking database fragmentation...
Warning: 410.48046875MB of free space (fragmented) detected
Vacuum is recommended to reclaim this space.

Do you want to continue with VACUUM? (y/N) y

Starting VACUUM... (this may take a few minutes)
Creating backup at /datadisk/Web2Lean/data/databases/web2lean.db.backup.20250103_171600.

✓ Vacuum completed in 8s
Database size: 423M → 12M

Verifying data integrity...
ok

Record counts after vacuum:
  questions: 1487
  answers: 1812
  processing_status: 1486

✓ Database vacuum completed successfully!
Backup saved at: /datadisk/Web2Lean/data/databases/web2lean.db.backup.20250103_171600
```

## 清理旧备份

备份文件会占用空间，定期清理：

```bash
# 删除所有数据库备份
rm /datadisk/Web2Lean/data/databases/web2lean.db.backup.*

# 只保留最近7天的备份
find /datadisk/Web2Lean/data/databases/ -name "web2lean.db.backup.*" -mtime +7 -delete
```

## 注意事项

1. **数据库锁定** - VACUUM期间会锁定数据库，确保：
   - 后端服务已停止
   - 或没有正在运行的数据导入/预处理任务

2. **执行时间** - 根据数据库大小，可能需要几秒到几分钟

3. **空间需求** - VACUUM需要额外的临时空间（约为数据库大小），确保磁盘有足够空间

4. **自动备份** - 脚本会自动创建备份，即使出错也能恢复

## 手动VACUUM命令

如果你想直接运行而不使用脚本：

```bash
sqlite3 /datadisk/Web2Lean/data/databases/web2lean.db "VACUUM;"
```

## 查看数据库状态

查看数据库当前大小和碎片：

```bash
# 查看文件大小
ls -lh /datadisk/Web2Lean/data/databases/web2lean.db

# 查看碎片情况
sqlite3 /datadisk/Web2Lean/data/databases/web2lean.db \
  "SELECT 'Free space: ' || freelist_count * page_size / 1024.0 / 1024.0 || ' MB'
   FROM pragma_page_count(), pragma_page_size(), pragma_freelist_count();"
```
