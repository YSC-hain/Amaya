PRAGMA foreign_keys = ON;

CREATE TABLE messages (
    message_id TEXT NOT NULL PRIMARY KEY,  -- ULID

    channel TEXT NOT NULL,
    metadata TEXT,

    role TEXT CHECK(role IN ('system', 'world', 'user', 'amaya')) NOT NULL,
    content TEXT NOT NULL,

    created_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE memory_groups (
    memory_group_id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    created_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE memory_points (
    memory_point_id INTEGER PRIMARY KEY AUTOINCREMENT,

    memory_group_id INTEGER NOT NULL,
    anchor TEXT NOT NULL,
    content TEXT NOT NULL,
    memory_type TEXT CHECK(memory_type IN ('fact', 'emotion', 'work')) NOT NULL,  -- 事实型记忆、情感型记忆、工作型记忆等
    weight REAL NOT NULL DEFAULT 1.0,

    created_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_group_id) REFERENCES memory_groups(memory_group_id)
);

-- 注意：此处的时间只精确到分钟，其格式为 "YYYY-MM-DD HH:MM"
CREATE TABLE reminders (
    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    remind_at_min_utc DATETIME NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending', 'triggered', 'sent')) NOT NULL DEFAULT 'pending', -- ToDo：暂时不考虑复杂的状态机设计
    --status TEXT CHECK(status IN ('pending', 'sent', 'acked', 'snoozed', 'escalated', 'ignored', 'cancelled')) NOT NULL DEFAULT 'pending',

    next_action_at_min_utc DATETIME DEFAULT NULL,
    created_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP
);
