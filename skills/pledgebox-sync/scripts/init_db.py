import os
from pathlib import Path
import pymysql
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def _require_env_vars(keys):
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)} (from {ENV_FILE})")

# ------------------------
# 获取数据库连接
# ------------------------

def get_connection(db=None):
    _require_env_vars(["MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER"])
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=db if db else None,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

# ------------------------
# 创建数据库（如果不存在）
# ------------------------

def create_database():
    db_name = os.getenv("MYSQL_DATABASE")
    if not db_name:
        raise ValueError("MYSQL_DATABASE 未设置")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                CREATE DATABASE IF NOT EXISTS `{db_name}`
                CHARACTER SET utf8mb4
                COLLATE utf8mb4_unicode_ci
            """)
        print(f"[INFO] 数据库 `{db_name}` 已就绪")
    finally:
        conn.close()

# ------------------------
# 创建所有表（如果不存在）
# ------------------------

def create_tables():
    db_name = os.getenv("MYSQL_DATABASE")
    if not db_name:
        raise ValueError("MYSQL_DATABASE 未设置")
    conn = get_connection(db_name)
    try:
        with conn.cursor() as cursor:
            # ---------------- orders ----------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                pbid VARCHAR(50) UNIQUE,
                order_status VARCHAR(50),
                survey_status VARCHAR(50),
                email VARCHAR(255),
                paid_amount DECIMAL(10,2),
                credit_offer DECIMAL(10,2),
                balance DECIMAL(10,2),
                courier_name VARCHAR(100),
                tracking_code VARCHAR(100),
                data_hash VARCHAR(64),
                is_active TINYINT DEFAULT 1,
                last_synced_at DATETIME,
                INDEX (pbid)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ---------------- order_addresses ----------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_addresses (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                order_id BIGINT,
                recipient_name VARCHAR(255),
                phone VARCHAR(50),
                address_line1 VARCHAR(255),
                city VARCHAR(100),
                state VARCHAR(100),
                country VARCHAR(100),
                country_code VARCHAR(10),
                zip VARCHAR(20),
                geo_status VARCHAR(20),
                INDEX (order_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ---------------- order_items ----------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                order_id BIGINT,
                source_type VARCHAR(20),
                product_id BIGINT,
                name VARCHAR(255),
                sku VARCHAR(100),
                price DECIMAL(10,2),
                quantity INT,
                INDEX (order_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ---------------- item_variants ----------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_variants (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                item_id BIGINT,
                variant_key VARCHAR(100),
                variant_value VARCHAR(255),
                INDEX (item_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ---------------- item_questions ----------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_questions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                item_id BIGINT,
                question TEXT,
                answer TEXT,
                INDEX (item_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # ---------------- geo_reference ----------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS geo_reference (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                country_code VARCHAR(10),
                zip VARCHAR(20),
                city VARCHAR(100),
                state VARCHAR(100),
                INDEX (country_code),
                INDEX (zip)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

        print("[INFO] 所有数据表已创建或已存在")
    finally:
        conn.close()

# ------------------------
# 初始化入口（供 sync.py 调用）
# ------------------------

def init_all():
    print("🚀 初始化数据库环境...")
    create_database()
    create_tables()
    print("🎉 数据库初始化完成")

# ------------------------
# CLI 运行入口
# ------------------------

if __name__ == "__main__":
    init_all()
