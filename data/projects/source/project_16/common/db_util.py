import re
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from config.settings import env_handler
from common.base_log import logger


# 允许操作的表名白名单，防止SQL注入
ALLOWED_TABLES = frozenset([
    'dsp_organization',
    'dsp_user',
    'dsp_role',
    'dsp_member',
    'dsp_team',
    'dsp_supplier',
])


class PostgresDB:
    """PostgreSQL 数据库操作封装"""

    # 表名合法字符：字母、数字、下划线
    _TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(self):
        self._conn_params = None

    def _validate_table_name(self, table: str):
        """验证表名合法性，防止SQL注入"""
        if not isinstance(table, str):
            raise ValueError(f"表名必须为字符串类型: {table!r}")

        if not self._TABLE_NAME_PATTERN.match(table):
            raise ValueError(f"非法表名(仅允许字母、数字、下划线): {table!r}")

        if ALLOWED_TABLES and table not in ALLOWED_TABLES:
            raise ValueError(f"不允许操作该表: {table}，允许的表: {sorted(ALLOWED_TABLES)}")

    @staticmethod
    def _quote_identifier(name: str) -> str:
        """用双引号包裹标识符，防止关键字冲突"""
        return f'"{name}"'

    def _get_conn_params(self) -> dict:
        """从配置获取数据库连接参数"""
        if self._conn_params is None:
            db_config = env_handler.get_database_config()
            self._conn_params = {
                "host": db_config.get("host", "localhost"),
                "port": db_config.get("port", 5432),
                "user": env_handler.get_env_variable("DB_USERNAME") or db_config.get("username", ""),
                "password": env_handler.get_env_variable("DB_PASSWORD") or db_config.get("password", ""),
                "dbname": db_config.get("database", ""),
            }
        return self._conn_params

    # ======================== 连接管理 ========================

    @contextmanager
    def get_connection(self, autocommit: bool = False):
        """获取数据库连接（上下文管理器）"""
        params = self._get_conn_params()
        conn = None
        try:
            conn = psycopg2.connect(**params)
            conn.autocommit = autocommit
            logger.debug(f"数据库连接成功: {params['host']}:{params['port']}/{params['dbname']}")
            yield conn
        except psycopg2.Error as e:
            logger.error(f"数据库连接失败: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(self, cursor_class=RealDictCursor, autocommit: bool = False):
        """获取游标（上下文管理器，自动提交/回滚）"""
        with self.get_connection(autocommit=autocommit) as conn:
            cursor = conn.cursor(cursor_factory=cursor_class)
            try:
                yield cursor
                if not autocommit:
                    conn.commit()
                    logger.debug("事务已提交")
            except Exception as e:
                if not autocommit:
                    conn.rollback()
                    logger.error(f"事务回滚: {e}")
                raise
            finally:
                cursor.close()

    # ======================== 基础操作 ========================

    def execute(self, sql: str, params: Optional[tuple] = None) -> int:
        """执行SQL（INSERT/UPDATE/DELETE），返回受影响行数"""
        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            rowcount = cursor.rowcount
            logger.info(f"执行SQL: {sql[:100]}... | 影响行数: {rowcount}")
            return rowcount

    def query_one(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """查询单条记录，返回字典或None"""
        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            logger.info(f"查询单条: {sql[:80]}... | 结果: {'有' if row else '无'}")
            return dict(row) if row else None

    def query_all(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """查询所有记录，返回字典列表"""
        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            logger.info(f"查询全部: {sql[:80]}... | 行数: {len(result)}")
            return result

    def query_value(self, sql: str, params: Optional[tuple] = None) -> Any:
        """查询单个值（如COUNT）"""
        with self.get_cursor(cursor_class=None) as cursor:
            cursor.execute(sql, params)
            value = cursor.fetchone()
            return value[0] if value else None

    # ======================== CRUD便捷方法 ========================

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """插入单条记录，返回受影响行数"""
        self._validate_table_name(table)
        columns = ", ".join(self._quote_identifier(k) for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {self._quote_identifier(table)} ({columns}) VALUES ({placeholders})"
        return self.execute(sql, tuple(data.values()))

    def insert_returning(self, table: str, data: Dict[str, Any], returning: str = "id") -> Any:
        """插入记录并返回指定字段"""
        self._validate_table_name(table)
        columns = ", ".join(self._quote_identifier(k) for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {self._quote_identifier(table)} ({columns}) VALUES ({placeholders}) RETURNING {self._quote_identifier(returning)}"
        with self.get_cursor() as cursor:
            cursor.execute(sql, tuple(data.values()))
            value = cursor.fetchone()
            result = dict(value).get(returning) if value else None
            logger.info(f"插入并返回: {table}.{returning}={result}")
            return result

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: Optional[tuple] = None) -> int:
        """更新记录"""
        self._validate_table_name(table)
        set_clause = ", ".join([f"{self._quote_identifier(k)} = %s" for k in data.keys()])
        sql = f"UPDATE {self._quote_identifier(table)} SET {set_clause} WHERE {where}"
        params = tuple(data.values()) + (where_params or ())
        return self.execute(sql, params)

    def delete(self, table: str, where: str, params: Optional[tuple] = None) -> int:
        """删除记录"""
        self._validate_table_name(table)
        sql = f"DELETE FROM {self._quote_identifier(table)} WHERE {where}"
        return self.execute(sql, params)

    # ======================== 查询辅助方法 ========================

    def count(self, table: str, where: str = "1=1", params: Optional[tuple] = None) -> int:
        """统计记录数"""
        self._validate_table_name(table)
        return self.query_value(f"SELECT COUNT(*) FROM {self._quote_identifier(table)} WHERE {where}", params)

    def exists(self, table: str, where: str, params: Optional[tuple] = None) -> bool:
        """判断记录是否存在"""
        return self.count(table, where, params) > 0

    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行SQL"""
        with self.get_cursor() as cursor:
            cursor.executemany(sql, params_list)
            rowcount = cursor.rowcount
            logger.info(f"批量执行: {sql[:80]}... | 影响行数: {rowcount}")
            return rowcount

    def reset_config(self):
        """重置连接参数（环境切换后调用）"""
        self._conn_params = None
        logger.info("数据库连接参数已重置")


pg_db = PostgresDB()
