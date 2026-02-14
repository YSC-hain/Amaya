# Amaya 单用户模式迁移说明

## 概述

本次更新将 Amaya 从多用户设计改为纯粹的单用户个人助手模式。所有用户相关的数据移至环境变量配置，简化了架构。

## 主要变更

### 1. 数据库架构变更

- **删除 `users` 表**：不再需要用户表
- **删除外键**：所有表（messages, reminders, memory_groups, memory_points）中的 `user_id` 字段和外键约束已被移除

### 2. 环境变量配置

新增以下环境变量（在 `.env` 文件中配置）：

```bash
# 用户个人信息
USER_NAME=用户名
USER_TIMEZONE=Asia/Shanghai
USER_EMAIL=

# 主联系方式: telegram 或 qq
PRIMARY_CONTACT_METHOD=telegram

# Telegram Bot 配置
ENABLE_TELEGRAM_BOT_POLLING=true
TELEGRAM_BOT_TOKEN=你的_telegram_bot_token
PRIMARY_TELEGRAM_USER_ID=你的_telegram_user_id

# QQ / NapCat 配置
ENABLE_QQ_NAPCAT=false
PRIMARY_QQ_USER_ID=0
```

### 3. 移除的环境变量

以下环境变量已被移除：
- `ALLOWED_TELEGRAM_USER_IDS` -> 替换为 `PRIMARY_TELEGRAM_USER_ID`
- `ADMIN_TELEGRAM_USER_ID` -> 不再需要
- `ALLOWED_QQ_USER_IDS` -> 替换为 `PRIMARY_QQ_USER_ID`
- `DEDEFAULT_TIMEZONE` -> 替换为 `USER_TIMEZONE`

### 4. 代码变更

#### 核心模块
- **orchestrator.py**: 移除 `user_id` 绑定逻辑，简化为单用户模式
- **storage/** 模块: 所有数据库操作移除 `user_id` 参数
- **datamodel.py**: 删除 `UserInfo` 数据模型，`IncomingMessage` 和 `OutgoingMessage` 移除 `user_id` 字段

#### 功能模块
- **functions/**: 工具函数不再需要 `user_id` 参数
- **llm/**: LLM 客户端不再接收 `user_id` 参数

#### 通道模块  
- **telegram_polling.py**: 使用 `PRIMARY_TELEGRAM_USER_ID` 进行认证
- **qq_onebot_ws.py**: 使用 `PRIMARY_QQ_USER_ID` 进行认证

## 迁移步骤

### 1. 备份现有数据库

```bash
cp data/amaya.db data/amaya.db.backup
```

### 2. 删除旧数据库（或手动迁移）

由于数据库结构发生重大变化，建议删除旧数据库重新开始：

```bash
rm data/amaya.db
```

如需保留历史数据，需要手动执行 SQL 迁移：

```sql
-- 删除外键约束需要重建表
-- messages 表
CREATE TABLE messages_new (
    message_id TEXT NOT NULL PRIMARY KEY,
    channel TEXT NOT NULL,
    metadata TEXT,
    role TEXT CHECK(role IN ('system', 'world', 'user', 'amaya')) NOT NULL,
    content TEXT NOT NULL,
    created_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO messages_new SELECT message_id, channel, metadata, role, content, created_at_utc FROM messages;
DROP TABLE messages;
ALTER TABLE messages_new RENAME TO messages;

-- reminders, memory_groups, memory_points 表类似处理
-- 最后删除 users 表
DROP TABLE users;
```

### 3. 配置环境变量

复制 `.env.example` 到 `.env` 并填写你的配置：

```bash
cp .env.example .env
# 编辑 .env 文件，填写你的个人信息和API密钥
```

### 4. 启动应用

```bash
python src/main.py
```

## 注意事项

1. **主联系方式**：`PRIMARY_CONTACT_METHOD` 必须设置为 `telegram` 或 `qq`，这决定了 Amaya 主动发送消息（如提醒）时使用的通道

2. **用户认证**：现在只有 `PRIMARY_TELEGRAM_USER_ID` 或 `PRIMARY_QQ_USER_ID` 指定的用户可以访问 Bot

3. **时区设置**：所有时间相关功能现在使用 `USER_TIMEZONE` 环境变量

4. **数据隔离**：由于移除了用户表，所有数据现在默认属于唯一的用户

## 常见问题

**Q: 我可以支持多个 Telegram/QQ 账号吗？**  
A: 不可以。这个版本是纯单用户模式，只能配置一个主 Telegram ID 和一个主 QQ ID。

**Q: 如何在 Telegram 和 QQ 之间切换？**  
A: 修改 `PRIMARY_CONTACT_METHOD` 环境变量即可。

**Q: 旧的对话历史和提醒会保留吗？**  
A: 如果你执行了手动 SQL 迁移，历史数据会保留。否则需要重新开始。

## 文件清单

### 新增文件
- `.env.example`: 环境变量配置示例

### 删除的文件
- `src/storage/user.py`: 用户存储模块

### 修改的文件
- `src/config/settings.py`: 环境变量配置
- `src/datamodel.py`: 数据模型
- `src/storage/sql/db_init_v1.sql`: 数据库初始化脚本
- `src/storage/message.py`: 消息存储
- `src/storage/reminder.py`: 提醒存储
- `src/storage/work_memory.py`: 记忆存储
- `src/core/orchestrator.py`: 核心编排器
- `src/functions/*.py`: 所有工具函数
- `src/llm/*.py`: LLM 客户端
- `src/channels/*.py`: 所有通道适配器
- `src/main.py`: 主入口
