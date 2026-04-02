import sqlite3
import hashlib
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'stocksphere.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def hash_password(password):
    salt = "stocksphere_salt_v1"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','manager','staff','finance')),
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'pcs',
            current_stock INTEGER DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 10,
            unit_price REAL NOT NULL DEFAULT 0,
            opening_stock INTEGER DEFAULT 0,
            total_in INTEGER DEFAULT 0,
            total_out INTEGER DEFAULT 0,
            supplier TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_type TEXT NOT NULL CHECK(txn_type IN ('INWARD','OUTWARD','RETURN','ADJUSTMENT')),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            party TEXT NOT NULL,
            unit_price REAL,
            reason TEXT,
            remarks TEXT,
            txn_date TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            username TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            detail TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    _seed(conn)
    conn.close()

def _seed(conn):
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    users = [
        ('Admin User',   'admin',   hash_password('admin123'),   'admin'),
        ('Rahul Sharma', 'rahul',   hash_password('staff123'),   'staff'),
        ('Anjali Verma', 'anjali',  hash_password('manager123'), 'manager'),
        ('Finance User', 'finance', hash_password('finance123'), 'finance'),
        ('Priya Gupta',  'priya',   hash_password('staff123'),   'staff'),
    ]
    c.executemany("INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)", users)
    conn.commit()

    uid = {row[0]: row[1] for row in c.execute("SELECT username, id FROM users").fetchall()}

    products = [
        ('ELEC-001','Circuit Board A3',   'Electronics',  'pcs',   340, 50,  480, 300,100, 60,'ABC Distributors'),
        ('ELEC-002','DC Motor 12V',        'Electronics',  'pcs',    82, 30, 1200, 100, 20, 38,'Tech World'),
        ('RAW-001', 'Steel Rod 10mm',      'Raw Materials','kg',   1200,200,   45,1000,400,200,'Sharma Enterprises'),
        ('RAW-002', 'Aluminium Sheet 2mm', 'Raw Materials','kg',     88,100,  320,  90, 50, 52,'Metro Metals'),
        ('PKG-001', 'Bubble Wrap Roll',    'Packaging',   'rolls',   18, 40,   90,  50, 10, 42,'Pack Masters'),
        ('PKG-002', 'Cardboard Box L',     'Packaging',   'pcs',      9, 60,   25,  70,  0, 61,'BoxCo'),
        ('TOOL-001','Hand Drill 500W',     'Tools',       'pcs',     15, 10, 2200,  12,  5,  2,'ToolKing'),
        ('TOOL-002','Measuring Tape 5m',   'Tools',       'pcs',      7, 15,  150,  20,  0, 13,'ToolKing'),
        ('CONS-001','Industrial Gloves L', 'Consumables', 'pairs',  220, 50,   35, 200,100, 80,'Safety First'),
        ('CONS-002','Cutting Disc 4"',     'Consumables', 'pcs',    145, 30,   22, 100, 80, 35,'Abrasives Ltd'),
    ]
    c.executemany("""INSERT INTO products(sku,name,category,unit,current_stock,reorder_level,
        unit_price,opening_stock,total_in,total_out,supplier) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", products)
    conn.commit()

    today = datetime.now()
    # (txn_type, product_id, qty, party, unit_price, reason, days_ago, username)
    txns_raw = [
        ('INWARD',  1,100,'ABC Distributors',  480,'Purchase Order',15,'admin'),
        ('INWARD',  3,400,'Sharma Enterprises', 45,'Purchase Order',12,'rahul'),
        ('OUTWARD', 5, 32,'Production Floor',  None,'Internal Use', 10,'priya'),
        ('OUTWARD', 4, 52,'Sales Dept',         None,'Sale Order',   8,'rahul'),
        ('INWARD',  2, 20,'Tech World',        1200,'Replenishment', 7,'rahul'),
        ('OUTWARD', 6, 61,'External Customer',  None,'Sale Order',   5,'priya'),
        ('INWARD',  9,100,'Safety First',        35,'Monthly order', 4,'admin'),
        ('OUTWARD', 7,  2,'Production Floor',  None,'Internal Use',  3,'rahul'),
        ('OUTWARD', 8, 13,'Sales Dept',          None,'Sale Order',  2,'priya'),
        ('INWARD', 10, 80,'Abrasives Ltd',       22,'Reorder',       1,'rahul'),
        ('OUTWARD', 2, 38,'Sales Dept',          None,'Sale Order',  1,'admin'),
    ]
    for t in txns_raw:
        txn_type, product_id, qty, party, price, reason, days_ago, uname = t
        txn_date = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        c.execute("""INSERT INTO transactions(txn_type,product_id,quantity,party,unit_price,
            reason,txn_date,username,user_id) VALUES(?,?,?,?,?,?,?,?,?)""",
            (txn_type, product_id, qty, party, price, reason, txn_date, uname, uid[uname]))

    audit_entries = [
        ('USER_LOGIN',      'admin',           'User admin signed in',                      'admin', 'admin'),
        ('PRODUCT_ADD',     'Circuit Board A3','Product ELEC-001 registered, stock: 300',   'admin', 'admin'),
        ('STOCK_INWARD',    'Circuit Board A3','Received 100 pcs from ABC Distributors',    'rahul', 'rahul'),
        ('STOCK_INWARD',    'Steel Rod 10mm',  'Received 400 kg from Sharma Enterprises',   'rahul', 'rahul'),
        ('STOCK_OUTWARD',   'Bubble Wrap Roll','Dispatched 32 rolls to Production Floor',   'priya', 'priya'),
        ('LOW_STOCK_ALERT', 'Cardboard Box L', 'Stock (9) at or below reorder level (60)',  None,     None),
    ]
    for action, entity, detail, uname, uid_key in audit_entries:
        user_id = uid.get(uid_key) if uid_key else None
        c.execute("INSERT INTO audit_logs(action,entity,detail,username,user_id) VALUES(?,?,?,?,?)",
                  (action, entity, detail, uname, user_id))

    conn.commit()
    print("Database seeded with demo data.")

if __name__ == '__main__':
    init_db()
    print("DB initialized at", DB_PATH)
