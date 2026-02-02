# Amaya 设计文档
Version：1.1.0-260202

## 项目定位
Amaya 是面向单用户的个人助手。未来可能支持多用户部署，但每个用户的数据完全独立存储。

## 术语表

| 术语 | 英文 | 定义 |
|-----|------|-----|
| 任务 | Task | 需要追踪、分解或完成的工作项。通常有截止日期、优先级等属性，可能跨越多天。 |
| 日程项 | ScheduleItem | 当日具体要做的事项，有精确的提醒时间。通常由 Task 生成，也可由用户口头要求创建。 |
| 任务列表 | TaskList | 任务的顶层分类容器，如 Inbox、Task、Routine、Checklist 等。 |
| 任务分组 | TaskGroup | TaskList 下的二级分类，用于组织相关任务。 |
| 提醒 | Reminder | 在指定时间向用户发送通知的行为，可通过 Telegram、Email 等渠道执行。 |
| 事实型记忆 | Factual Memory | 用户偏好、作息规律、个人规则等具有长效性的信息。 |
| 工作型记忆 | Working Memory | 近期任务上下文、对话历史等短期信息，会随时间更新或压缩。 |
| 世界上下文 | World Context | 每次调用 LLM 前注入的环境信息，包括当前时间、今日日程、近期任务等。 |
| 固定时间事件 | Fixed-time Event | 必须在特定时间进行的活动，如会议、上课等，不可随意调整。 |
| 会话 | Session/Conversation | 一次连续的对话交互，从发起到自然结束 |
| 主动会话 | Proactive Session | Amaya 主动发起的非提醒类对话，如早间问候、进度跟进等。 |
| 勿扰时间 | Do Not Disturb | 用户设定的不希望被打扰的时段，仅影响主动会话，不影响提醒。 |
| 优先级 | Priority | 任务或日程的重要程度，分为 High、Medium、Low、None 四级。 |
| 工具函数 | Tool Function | LLM 可调用的函数，用于执行操作或获取信息（如创建任务、查询天气） |
| 升级提醒 | Escalation | 当普通提醒无响应时，通过更可靠渠道的二次通知 |
| 上下文窗口 | Context Window | LLM 单次调用可处理的最大 Token 数 |


## 触发主动对话的场景
主动对话的时间窗口应根据用户作息动态分析得出（ToDo）  
- 早间问候 + 今日日程概览
- 任务进度跟进
- 发现用户可能遗忘任务时的友好提醒
- 晚间全天回顾与次日安排

### 勿扰时间规则
勿扰时间仅影响**主动会话**（问候、进度跟进等），**不影响提醒消息**的发送。


## 技术选型
- Python 版本: 3.12+
- 数据库: SQLite（每用户独立数据库文件）
- 定时任务: APScheduler（使用 SQLite 作为 Job Store 实现持久化）
- LLM 接口: 兼容 OpenAI API 格式的第三方服务
- 通讯平台: Telegram Bot API

### LLM 调用降级策略
当主 LLM API 调用失败时，按以下顺序处理：
1. 备用接口：切换到备用API
2. 降级处理：
   - 提醒场景：发送模板化的提醒消息（包含任务标题和时间）
   - 对话场景：向用户返回友好的错误提示，建议稍后重试

### 提醒系统策略

#### 二次提醒与重复提醒
| 优先级 | 首次提醒后 5 分钟无响应 | 后续重复提醒 |
|--------|------------------------|-------------|
| High | Telegram + Email | 每 3 分钟重复，最多 3 次 |
| Medium | Email | 不重复 |
| Low | 不触发 | 不重复 |
| None | 不触发 | 不重复 |

#### ScheduleItem 自动生成
- 每天凌晨（用户时区 00:00）自动扫描当日需要提醒的 Task
- 根据 Task 的 `reminder_time_utc` 字段生成对应的 ScheduleItem
- 一个 Task 在同一天可能生成多个 ScheduleItem（如多次提醒）

### 异常处理与数据备份（ToDo）
该部分暂时不需要实现，仅作记录：
- 网络中断时的本地缓存策略
- 数据库损坏时的恢复机制
- Telegram API 限流时的退避策略
- SQLite 数据库定期备份机制
- 进程崩溃重启后错过任务的补发逻辑

### 记忆系统

#### 事实型记忆（ToDo）
用户偏好、作息规律、个人规则等长期信息。
技术选型待定，可考虑使用开源记忆系统替代。

#### 工作型记忆
近期任务上下文、当前对话历史等短期信息。
暂时决定采用 Markdown 文件存储，便于调试和人工审查。

存储位置：`./data/{user_id}/work_memory/`

| 文件 | 用途 | 更新时机 |
|------|------|----------|
| conversation.md | 被压缩的历史对话摘要 | 当对话上下文超出系统策略的限制时，由 LLM 通过 function call 生成滚动式摘要 |
| plan.md | 当前进行中的计划与目标 | 计划变更时，由 LLM 通过 function call 更新 |
| context.md | 当前工作上下文（正在做什么） | 任务状态变更时，由 LLM 通过 function call 更新 |

#### 对话上下文管理
对话历史采用「近期原文 + 远期摘要」的混合策略：
1. 近期对话：保留在 API 的 messages 参数中，作为多轮对话上下文直接传递给 LLM
2. 远期对话：当对话轮数或 Token 长度超过阈值时，由 LLM 生成摘要并追加到 conversation.md，原始对话从 messages 中移除
3. 加载时：conversation.md 的内容作为 system prompt 的一部分，提供历史上下文

抽象接口：
```
class WorkingMemory:
    def load(file_name: str) -> str
    def save(file_name: str, content: str) -> None
    def append(file_name: str, content: str) -> None
```

----

## 大致架构

### src/llm/ - LLM 模块
设计模式：依赖注入

- base.py: 抽象基类 LLMClient, 数据模型（Message, FunctionCall, LLMResponse 等）, 异常定义（LLMError, LLMUnavailableError 等）
- openai_client.py: OpenAI 兼容接口实现
- mock_client.py: Mock 实现，开启一个新的终端窗口输出请求内容，并接受用户的输入作为 LLM 的返回；支持 Function Call

### src/messaging/ - 通讯模块（Telegram Bot 实现）

- telegram_bot.py

限制：当前版本仅支持私聊场景，不支持群组。

#### 至少支持的命令
| 命令 | 功能 |
|------|------|
| /start | 初始化 Bot，绑定用户 |
| /online | 检查服务是否在线及服务器状态 |
| /today | 查看今日日程 |
| /help | 显示帮助信息 |

命令交互规范：
- 响应后删除用户发送的指令消息
- 回复消息下方附带"关闭"按钮，点击后清除该回复

### src/storage/ - 存储与数据持久化系统

- user.py: 负责管理用户数据库与鉴权
- storage.py: 数据存储实现模块

### src/core/ - Agent 核心模块

- orchestrator.py: 核心逻辑模块
- conversation.py: 对话管理服务
- memory.py: 记忆模块
- task.py: 任务模块（负责任务的读取，设置，写入）
- schedule.py：日程模块
- reminder.py：提醒发送逻辑
- timer.py: 定时器模块（在指定时间触发回调）

### src/config/ - 配置管理

- settings.py: 全局配置（LLM API密钥、超时时间等）
- prompts.py: Prompt模板管理（人设定义、世界上下文模板）
- logging.py: 日志配置（TRACE 级别支持）

### src/functions/ - 工具函数模块

- registry.py: 工具函数注册器
- task_functions.py: 任务相关工具
- info_functions.py: 信息查询工具
- memory_functions.py: 记忆相关工具
- schedule_functions.py: 日程相关工具

### 根目录

- main.py: 协调所有模块
- .env.example: 环境变量示例
- .env: 环境变量配置 (gitignore)

## 数据模型
注意：此处是单用户下的数据模型，对于不同的用户，我们计划直接使用不同的数据库或是存储文件夹（因为可能要兼容其它开源的记忆系统）
ID一律使用`ULID`来计算。

### Task 部分
这主要参考了GTD时间管理法。
TaskList > TaskGroup > Task > subTask

#### TaskList
- task_list_id: TaskList id
- name
- updated_at_utc

TaskList 通常有 Inbox, Task, Routine, Checklist 等

#### TaskGroup
- task_group_id: TaskGroup id
- task_list_id: 标识其属于哪个TaskList
- name
- updated_at_utc

#### Task
- task_id: Task id
- task_list_id：必填
- task_group_id：可选（NULL 表示直接属于 TaskList）
- title
- content
- priority：优先级：包括 High, Medium, Low, None
- status: 状态，包括 todo,done,cancelled
- created_at_utc
- updated_at_utc
- completed_at_utc
- estimated_duration_minutes
- is_fixed_time_event: 是否为固定时间（如上课、会议等必须在指定时间进行的活动）
- start_at_utc：有固定时间的Task的开始时间
- end_at_utc
- due_at_utc: 截止时间（需要在指定时间前完成的任务）
- reminder_time_utc (一般精确到分钟)
- reminder_prompt
- recurrence_rule: str | None（iCal RRULE 格式，如 "FREQ=DAILY;INTERVAL=1"）
- recurrence_end_at_utc: datetime | None
- parent_task_id: 父任务 ID（子任务与 Task 同表，通过此字段自关联，支持多层嵌套但不推荐）
- blocked_by_task_id：依赖的任务/前置任务
- attachments: 附件文件路径列表

### Schedule - 日程部分
该部分由Amaya维护和管理。与Task部分不同，这里的内容是：“今天/明天具体要做哪些事”。
日程一般由Task或某个Task的具体步骤组成, 也可以由用户的口头要求创建（比如：”五分钟后提醒我关掉燃气灶“）。
Task 与 ScheduleItem 的主要区别在于：Task 是较为严肃的，通常是需要追踪或是分解的；而 ScheduleItem 是微小，具体且在今天的，它通常没必要写成一个Task，且有准确的提醒时间。

#### ScheduleItem - 日程的组成项目
ScheduleItem 本身不追踪状态，它的职责是在指定时间触发提醒。一个 Task 可以产生多个 ScheduleItem。

- schedule_item_id: ScheduleItem id
- title: 日程标题
- reminder_prompt: 用于生成提醒消息时传给 LLM 的上下文信息
- priority: 优先级（High, Medium, Low, None）
- created_at_utc
- reminder_time_utc: 提醒触发时间
- task_id: 关联的 Task ID（可选）
- is_sent: 是否已发送提醒
- acknowledgment_status: 提醒状态（见下方状态机定义）
- snoozed_until_utc: datetime | null
- last_reminded_at_utc: datetime | null
- retry_count: int (记录重复提醒次数)
- origin: 'task' | 'quick_command' | 'recurring' | ...（来源类型）
- channel: 'telegram' | 'email' （发送渠道偏好）

#### Schedule 发送提醒的状态机

| 状态 | 含义 | 说明 |
|------|------|------|
| `pending` | 待发送 | 初始状态，等待到达提醒时间 |
| `sent` | 已发送 | 提醒已通过主渠道（Telegram）发送，等待用户响应 |
| `acked` | 已确认 | 用户已确认收到（回复消息或点击"收到"按钮等） |
| `snoozed` | 已延后 | 用户选择延后提醒，将在 `snoozed_until_utc` 时间重新触发 |
| `escalated` | 已升级 | 用户超时未响应，已通过备用渠道进行二次提醒 |
| `ignored` | 已忽略 | 用户点击"本次取消"，或所有提醒尝试均无响应 |
| `cancelled` | 已取消 | 提醒被系统或用户主动取消（如关联的 Task 被删除） |


| 当前状态 | 触发条件 | 目标状态 | 备注 |
|---------|----------|----------|------|
| `pending` | 到达 `reminder_time_utc` | `sent` | 发送提醒消息 |
| `pending` | Task 被删除/取消 | `cancelled` | - |
| `sent` | 用户点击"收到"或回复消息 | `acked` | 终态 |
| `sent` | 用户点击"延后" | `snoozed` | 需设置 `snoozed_until_utc` |
| `sent` | 用户点击"本次取消" | `ignored` | 终态 |
| `sent` | 5 分钟超时 + High 优先级 | `escalated` | 触发 Email 二次提醒 |
| `sent` | 5 分钟超时 + Medium 优先级 | `escalated` | 触发 Email 二次提醒（不重复） |
| `sent` | 5 分钟超时 + Low/None 优先级 | `ignored` | 不触发二次提醒，终态 |
| `snoozed` | 到达 `snoozed_until_utc` | `pending` | 重新进入待发送状态 |
| `escalated` | 用户响应 | `acked` | 终态 |
| `escalated` | High 优先级 + 3 分钟超时 | `escalated` | 重复提醒，`retry_count` +1，最多 3 次 |
| `escalated` | High 优先级 + 重试次数达到 3 次 | `ignored` | 终态，记录为未响应 |
| `escalated` | Medium 优先级 + 超时 | `ignored` | 终态，不重复提醒 |


-----

### Event - 事件队列
整个系统涉及延迟发送、重试等逻辑。据此引入一个简单的消息/事件抽象层：

- event_id: str
- event_type: str ('reminder_due', 'escalation_needed', etc.)
- payload: dict
- scheduled_at_utc: datetime

### Reminder 部分
Reminder 是指执行提醒任务的具体方式。可以有 Telegram Bot, email 等。

### User 部分 - 用户配置
- user_id
- timezone: 时区（IANA 格式）
- email: 用于二次提醒
- language_style: 语言风格偏好（formal / casual）
- telegram_user_id: 关联的 Telegram 用户 ID

## 对于可能的数据迁移
采用自实现的简单版本管理，手动执行迁移命令。
每个数据库文件记录当前 schema 版本号，迁移脚本按版本顺序执行。

## 日志系统
- 级别: TRACE / DEBUG / INFO / WARNING / ERROR / FATAL
- 控制台输出: INFO 及以上
- 文件输出: 所有级别

### 日志内容规范
| 级别 | 典型内容 |
|------|----------|
| TRACE | LLM API 完整请求体与响应体（用于调试） |
| DEBUG | 函数调用参数、中间状态 |
| INFO | 用户消息收发、任务状态变更、提醒触发 |
| WARNING | 非致命异常、API 重试 |
| ERROR | API 调用失败、数据操作异常 |
| FATAL | 服务无法启动、不可恢复错误 |

重要：TRACE 级别需完整记录 LLM API 的请求体（包括 messages、functions、model 等参数）和响应体，便于调试时 review 对话上下文和 Function Call 行为。

## 工具函数
对于每个工具函数，都要定义 (name, description, input_schema, output_schema, retry_strategy, fallback_value)，并考虑失败重试策略。

**注意**：某些常用信息应该在调用 LLM 前由 Agent 获取，放入 World Context 传给 LLM，以节省 Token 成本。

### 预置到 World Context 的信息
更新时机：每次调用 LLM 前实时获取。

- 当前日期时间（用户时区）
- 今日日程概览
- 近期未完成的任务（按优先级排序）
- 工作型记忆内容（从 Markdown 文件加载）

### 主要的一部分工具函数
- get_weather: 获取天气信息
- get_holidays: 获取节假日信息
- list_tasks: 列出任务（支持按状态、优先级、日期筛选）
- create_task: 创建任务
- update_task: 更新任务
- mark_task_done: 标记任务完成
- delete_task: 删除任务
- list_today_schedule: 列出今日日程
- add_schedule_item: 创建日程项
- snooze_reminder: 延迟提醒
- update_conversation_summary: 更新对话摘要（滚动式追加）
- update_memory_plan: 更新当前计划
- update_memory_context: 更新工作上下文

- cancel_task: 取消任务（与 delete_task 不同，保留记录）
- get_task_detail: 获取任务详情
- search_tasks: 按关键词搜索任务
- get_upcoming_schedule: 获取未来 N 天的日程
- acknowledge_reminder: 确认收到提醒（供 Telegram 按钮回调使用）


## 示例
### 添加新任务
如果用户发来的消息中包含了新的任务（指用户学习或工作中产生的任务），Amaya需要分析并将其格式化为Task,在询问用户后将其持久化并关联对应的TaskList与TaskGroup等。如果是特别简单或清晰的任务，或者是普通的日程规划，Amaya可以直接将其添加到Schedule，但也需要向用户复述新增的内容。

## 典型用户故事

### 场景 1：快速提醒
**用户**：「五分钟后提醒我关掉燃气灶」

**Amaya 处理流程**：
1. 识别为简单的即时提醒，无需创建 Task
2. 直接创建 ScheduleItem（reminder_time_utc = 当前时间 + 5min，priority = High）
3. 回复用户：「好的，我会在 14:35 提醒你关掉燃气灶」
4. 5 分钟后触发提醒，LLM 生成消息：「记得关掉燃气灶哦！」

---

### 场景 2：创建带截止日期的任务
**用户**：「下周五之前要完成项目报告」

**Amaya 处理流程**：
1. 识别为需要追踪的任务
2. 提取信息并询问确认：「我帮你创建一个任务：\n- 标题：完成项目报告\n- 截止时间：2026-02-06（周五）\n- 优先级：Medium\n需要我设置提醒吗？」
3. 用户确认后，创建 Task 并持久化
4. 在之后的“日程安排”中，Amaya 应当考虑这个任务并建议用户将它排上日程，以确保在截止时间之前可以完成
5. 截止日的凌晨，自动生成 ScheduleItem，提前一定时间进行最后的提醒

---

### 场景 3：固定时间事件
**用户**：「明天下午三点有个会议」

**Amaya 处理流程**：
1. 识别为固定时间事件（is_fixed_time_event = true）
2. 询问确认：「我帮你记录一个会议：\n- 时间：2026-01-29 15:00\n- 提前 15分钟 提醒你可以吗？」
3. 用户回复「半小时」
4. 创建 Task（reminder_time_utc = 14:30）
5. 次日凌晨自动生成 ScheduleItem
6. 14:30 触发提醒：「你的会议将在半小时后开始，准备好了吗？」
