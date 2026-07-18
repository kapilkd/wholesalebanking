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


def _get_pool():
    """
    Lazily create and return a connection pool, built from DB_* env vars.

    Returns:
        mysql.connector.pooling.MySQLConnectionPool
    """
    global _pool
    if _pool is not None:
        return _pool

    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME")

    if not host or not port or not user or not database:
        raise ValueError(
            "Database configuration incomplete. DB_HOST, DB_PORT, DB_USER, and "
            "DB_NAME must be set in your .env file."
        )

    _pool = pooling.MySQLConnectionPool(
        pool_name="wholesale_banking_pool",
        pool_size=5,
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
    return _pool


def get_db_connection():
    """
    Get a pooled connection to the wholesale banking database.

    Returns:
        mysql.connector.connection.MySQLConnection
    """
    return _get_pool().get_connection()
