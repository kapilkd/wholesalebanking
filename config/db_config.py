"""
MySQL/MariaDB database configuration and connection factory
"""
import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling

# Load environment variables
load_dotenv()

_pool = None
_readonly_pool = None


def _build_pool(pool_name, user, password, pool_size=5):
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    database = os.getenv("DB_NAME")

    if not host or not port or not user or not database:
        raise ValueError(
            "Database configuration incomplete. DB_HOST, DB_PORT, DB_USER, and "
            "DB_NAME must be set in your .env file."
        )

    return pooling.MySQLConnectionPool(
        pool_name=pool_name,
        pool_size=pool_size,
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database,
        # Pure-Python protocol implementation. The C extension
        # (_mysql_connector) bundles its own protobuf/SSL and is a known
        # source of in-process conflicts with Streamlit's native stack
        # (protobuf/pyarrow); this app's queries are client-scoped and
        # small, so the C extension's speed advantage doesn't matter.
        use_pure=True,
    )


def _get_pool():
    """Lazily create the primary pool from DB_* env vars."""
    global _pool
    if _pool is None:
        _pool = _build_pool(
            "wholesale_banking_pool",
            os.getenv("DB_USER"),
            os.getenv("DB_PASSWORD", ""),
        )
    return _pool


def _get_readonly_pool():
    """
    Pool for LLM-generated chat queries. Uses the dedicated read-only
    credentials DB_RO_USER / DB_RO_PASSWORD when configured (strongly
    recommended: a role with SELECT-only grants, ideally on a replica);
    falls back to the primary credentials otherwise — the session is still
    forced READ ONLY at execution time either way (src/db_reader.py).
    """
    global _readonly_pool
    if _readonly_pool is None:
        ro_user = os.getenv("DB_RO_USER")
        if not ro_user:
            return _get_pool()
        _readonly_pool = _build_pool(
            "wholesale_banking_ro_pool",
            ro_user,
            os.getenv("DB_RO_PASSWORD", ""),
            pool_size=3,
        )
    return _readonly_pool


def get_db_connection():
    """
    Get a pooled connection to the wholesale banking database.

    Returns:
        mysql.connector.connection.MySQLConnection
    """
    return _get_pool().get_connection()


def get_readonly_db_connection():
    """Pooled connection for chat-generated SQL (read-only credentials if set)."""
    return _get_readonly_pool().get_connection()
