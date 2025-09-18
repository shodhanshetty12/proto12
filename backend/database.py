import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "irrigation.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Sensor data table
    c.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            soil_moisture REAL,
            temperature REAL,
            humidity REAL,
            pump_status TEXT
        )
    """)
    # Water usage table
    c.execute("""
        CREATE TABLE IF NOT EXISTS water_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            liters_used REAL
        )
    """)
    # Notifications table
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            message TEXT,
            type TEXT
        )
    """)
    # Settings key-value table
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_data(row):
    """Insert one row of simulation data into sensor_data table"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO sensor_data (timestamp, soil_moisture, temperature, humidity, pump_status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        row.get("timestamp") or "",
        row.get("soil_moisture"),
        row.get("temperature"),
        row.get("humidity"),
        row.get("pump_status") or "OFF"
    ))
    conn.commit()
    conn.close()

def fetch_all():
    """Fetch all rows from sensor_data"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM sensor_data ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def log_water_usage(timestamp, liters):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO water_usage (timestamp, liters_used) VALUES (?, ?)", (timestamp, liters))
    conn.commit()
    conn.close()

def fetch_water_usage():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM water_usage ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return data

def fetch_water_usage_total():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(liters_used), 0) FROM water_usage")
    total = c.fetchone()[0] or 0
    conn.close()
    return total

def log_notification(message: str, type_: str = "info", timestamp: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if not timestamp:
        import datetime
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO notifications (timestamp, message, type) VALUES (?, ?, ?)", (timestamp, message, type_))
    conn.commit()
    conn.close()

def fetch_notifications(limit: int = 10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, timestamp, message, type FROM notifications ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_setting(key: str, default: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if row and row[0] is not None:
        return row[0]
    return default

def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()
