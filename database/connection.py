import sqlite3
from contextlib import contextmanager
from pathlib import Path


def create_connection(database_path: str | Path, timeout: float = 60):
    """Mở kết nối riêng cho tác vụ; bên gọi chịu trách nhiệm đóng kết nối."""
    # Parent must exist: do not silently create a local substitute for a bad UNC path.
    path = Path(database_path)
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Không truy cập được thư mục database: {path.parent}")
    conn = sqlite3.connect(str(path), timeout=timeout, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
        return conn
    except BaseException:
        conn.close()
        raise


@contextmanager
def connection(database_path: str | Path, timeout: float = 60):
    """Cấp kết nối LI và luôn đóng sau tác vụ."""
    conn = create_connection(database_path, timeout)
    try:
        yield conn
    finally:
        conn.close()

