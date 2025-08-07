
import sqlite3
import json
import threading
from contextlib import contextmanager
from .state_manager import AmayaState
from .logger import event_logger

class PersistenceManager:
    """负责将特定用户的状态和记忆持久化到数据库。
    使用连接池确保线程安全。
    """
    def __init__(self, user_id: str, db_path='amaya.db'):
        self.db_path = db_path
        self.user_id = user_id
        # 验证 user_id
        if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
            raise ValueError(f"Invalid user_id: {user_id}")
        self.user_id = user_id.strip()
        # 使用线程本地存储确保线程安全
        self._local = threading.local()
        self._lock = threading.Lock()
        self._initialize_user_database()

    def _get_connection(self):
        """获取线程本地的数据库连接。"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    @contextmanager
    def transaction(self):
        """提供一个事务上下文管理器，自动处理提交和回滚。使用线程本地连接。"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            event_logger.log_event('DB_TRANSACTION_ERROR', {'error': str(e), 'user_id': self.user_id})
            print(f"[错误] 数据库事务失败: {e}")
            raise

    def _initialize_user_database(self):
        """初始化数据库，创建表，并确保当前用户存在于状态表中。"""
        try:
            with self.transaction() as conn:
                with conn:
                    cursor = conn.cursor()
                
                # 创建记忆表，增加 user_id 字段
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                ''')
                
                # 创建用户状态表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_states (
                        user_id TEXT PRIMARY KEY,
                        energy REAL,
                        mood TEXT,
                        favorability INTEGER,
                        current_action TEXT,
                        interaction_mode TEXT
                    )
                ''')

                # 检查当前用户是否存在，如果不存在则插入默认状态
                cursor.execute("SELECT user_id FROM user_states WHERE user_id = ?", (self.user_id,))
                if cursor.fetchone() is None:
                    default_state = AmayaState(self.user_id)  # 创建一个默认状态实例
                    cursor.execute('''
                        INSERT INTO user_states (user_id, energy, mood, favorability, current_action, interaction_mode)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        self.user_id, default_state.energy, default_state.mood, 
                        default_state.favorability, default_state.current_action, default_state.interaction_mode
                    ))
                    event_logger.log_event('USER_CREATED_IN_DB', {'user_id': self.user_id})

            event_logger.log_event('DB_INITIALIZED_FOR_USER', {'db_path': self.db_path, 'user_id': self.user_id})
        except sqlite3.Error as e:
            event_logger.log_event('DB_ERROR', {'error': f"Database initialization failed for user {self.user_id}: {e}"})
            print(f"[错误] 数据库初始化失败: {e}")

    def save_state(self, cursor, state: AmayaState):
        """
        使用提供的数据库游标将当前用户的核心状态保存到数据库。
        注意：此方法不执行 commit。
        """
        state_tuple = (
            state.energy,
            state.mood,
            state.favorability,
            state.current_action,
            state.interaction_mode,
            self.user_id
        )
        try:
            cursor.execute('''
                UPDATE user_states
                SET energy = ?, mood = ?, favorability = ?, current_action = ?, interaction_mode = ?
                WHERE user_id = ?
            ''', state_tuple)
            event_logger.log_event('STATE_SAVED_TO_DB_PENDING_COMMIT', {'user_id': self.user_id})
        except sqlite3.Error as e:
            event_logger.log_event('DB_ERROR', {'error': f"Failed to save state for user {self.user_id}: {e}"})
            print(f"[错误] 无法为用户 {self.user_id} 保存状态: {e}")


    def load_state(self, state: AmayaState) -> bool:
        """从数据库加载当前用户的核心状态。如果用户是新用户，则返回 False。"""
        try:
            conn = self._get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT energy, mood, favorability, current_action, interaction_mode FROM user_states WHERE user_id = ?", (self.user_id,))
                row = cursor.fetchone()
                
                if row:
                    state.energy, state.mood, state.favorability, state.current_action, state.interaction_mode = row
                    state.user_id = self.user_id
                    event_logger.log_event('STATE_LOADED_FROM_DB', {'user_id': self.user_id})
                    return True
                else:
                    event_logger.log_event('STATE_LOAD_SKIPPED', {'reason': f'User {self.user_id} not found in DB.', 'user_id': self.user_id})
                    return False
        except sqlite3.Error as e:
            event_logger.log_event('DB_ERROR', {'error': f"Failed to load state for user {self.user_id}: {e}"})
            print(f"[错误] 无法为用户 {self.user_id} 加载状态: {e}")
            return False

    def save_memory(self, cursor, memory_entry: dict):
        """
        使用提供的数据库游标将单条记忆实时存入 SQLite 数据库。
        注意：此方法不执行 commit。
        """
        try:
            cursor.execute('''
                INSERT INTO memories (user_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (self.user_id, memory_entry['role'], memory_entry['content'], memory_entry['timestamp']))
            event_logger.log_event('MEMORY_SAVED_TO_DB_PENDING_COMMIT', {'user_id': self.user_id})
        except sqlite3.Error as e:
            event_logger.log_event('DB_ERROR', {'error': f"Failed to save memory for user {self.user_id}: {e}"})
            print(f"[错误] 无法为用户 {self.user_id} 保存记忆到数据库: {e}")

    def load_full_memory_archive(self, state: AmayaState):
        """从 SQLite 加载特定用户的所有记忆到 state.full_memory_archive。"""
        try:
            conn = self._get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role, content, timestamp FROM memories WHERE user_id = ? ORDER BY timestamp ASC", (self.user_id,))
                rows = cursor.fetchall()
                
                state.full_memory_archive = [
                    {"role": row[0], "content": row[1], "timestamp": row[2]}
                    for row in rows
                ]
                event_logger.log_event('MEMORY_LOADED_FROM_DB', {'user_id': self.user_id, 'count': len(rows)})
        except sqlite3.Error as e:
            event_logger.log_event('DB_ERROR', {'error': f"Failed to load memories for user {self.user_id}: {e}"})
            print(f"[错误] 无法为用户 {self.user_id} 从数据库加载记忆: {e}")

    def close(self):
        """关闭数据库连接。"""
        with self._lock:
            if hasattr(self._local, 'conn') and self._local.conn:
                self._local.conn.close()
                self._local.conn = None
            event_logger.log_event('DB_CLOSED', {'user_id': self.user_id})

