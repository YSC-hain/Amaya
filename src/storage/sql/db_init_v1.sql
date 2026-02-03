PRAGMA foreign_keys = ON;

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC+8',  -- IANA时区
    email TEXT,
    telegram_user_id INTEGER UNIQUE,
    last_active_utc DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    message_id TEXT NOT NULL PRIMARY KEY,  -- ULID

    channel TEXT NOT NULL,
    user_id INTEGER NOT NULL,

    role TEXT CHECK(role IN ('system', 'world', 'user', 'amaya')) NOT NULL,
    content TEXT NOT NULL,

    created_at_utc DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
