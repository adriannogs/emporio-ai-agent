import sqlite3
from pathlib import Path
import pandas as pd
from .config import DATA_DIR, DB_PATH

TABLES = {
    "categories": "categories.csv",
    "customers": "customers.csv",
    "order_items": "order_items.csv",
    "orders": "orders.csv",
    "products": "products.csv",
    "promotions": "promotions.csv",
}

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database(force: bool = False):
    """Carrega os CSVs para SQLite. Repetível e sem duplicar dados."""
    with connect() as conn:
        if force:
            for table in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
        for table, filename in TABLES.items():
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if exists and not force:
                continue
            path = DATA_DIR / filename
            if not path.exists():
                raise FileNotFoundError(f"Arquivo de dados não encontrado: {path}")
            df = pd.read_csv(path)
            df.to_sql(table, conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_promotions_product ON promotions(product_id)")
        conn.commit()

def query(sql: str, params=()):
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
