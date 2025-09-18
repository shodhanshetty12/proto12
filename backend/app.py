from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pandas as pd
import threading
import time
import os

# --- Local imports ---
from hardware import hardware_bp
from database import (
    init_db,
    insert_data,
    fetch_all,
    log_water_usage,
    fetch_water_usage,
    fetch_water_usage_total,
    log_notification,
    fetch_notifications,
    get_setting,
    set_setting,
)

app = Flask(__name__)
CORS(app)  # allow frontend calls

# Register blueprints (AFTER app is created)
app.register_blueprint(hardware_bp)

# --- Paths ---
BASE_DIR = os.path.dirname(__file__)
DATA_CSV = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "sample_data.csv"))

# --- Simulation State ---
simulation_data = []
simulation_running = False
simulation_index = 0
current_row = None  # last processed row

# --- Mode State ---
# 'simulation' or 'hardware'
current_mode = "simulation"
last_pump_status = "OFF"


def run_simulation():
    global simulation_running, simulation_index, current_row, last_pump_status
    while simulation_running and simulation_index < len(simulation_data):
        # Get current row and compute pump + persist, so it works even if no client is polling
        row = simulation_data[simulation_index].copy()

        # Compute pump status based on soil moisture
        soil = float(row.get("soil_moisture", 500))
        try:
            threshold = float(get_setting("moisture_threshold", "500") or 500)
        except Exception:
            threshold = 500
        row["pump_status"] = 1 if soil < threshold else 0

        # Log water usage when pump is ON
        if row["pump_status"] == 1:
            liters_used = 2.0
            log_water_usage(row.get("timestamp"), liters_used)
            last_pump_status = "ON"
            try:
                log_notification("Pump turned ON by simulation", "info", row.get("timestamp"))
            except Exception:
                pass
        else:
            last_pump_status = "OFF"

        # Persist sensor row
        insert_data(row)

        # Expose latest row
        current_row = row

        # Advance to next step
        simulation_index += 1
        time.sleep(1)   # simulate 1 second per row

    simulation_running = False



# --- Health check ---
@app.route("/api/health")
def health_check():
    return jsonify({"status": "ok", "message": "Smart Irrigation backend is running!"})


@app.route("/api/simulation/start", methods=["POST"])
def start_simulation():
    global simulation_running, simulation_thread, simulation_index, simulation_data

    if current_mode == "hardware":
        return jsonify({"error": "Simulation disabled in hardware mode"}), 400
    if simulation_running:
        return jsonify({"status": "already_running"})

    if not os.path.exists(DATA_CSV):
        return jsonify({"error": f"CSV not found at {DATA_CSV}"}), 404

    # Load CSV fresh
    df = pd.read_csv(DATA_CSV)
    simulation_data = df.to_dict(orient="records")

    # reset index and state
    simulation_index = 0
    simulation_running = True

    # start background simulation
    simulation_thread = threading.Thread(target=run_simulation, daemon=True)
    simulation_thread.start()

    return jsonify({"status": "started", "total_rows": len(simulation_data)})



@app.route("/api/simulation/stop", methods=["POST"])
def stop_simulation():
    global simulation_running
    simulation_running = False
    return jsonify({"status": "stopped"})


@app.route("/api/simulation/data", methods=["GET"])
def get_simulation_data():
    # Return the latest processed row when running; otherwise return status
    if current_mode == "hardware":
        return jsonify({"status": "hardware_mode"})
    if not simulation_running and current_row is None:
        return jsonify({"status": "stopped"})
    if simulation_running is False and simulation_index >= len(simulation_data) and len(simulation_data) > 0:
        return jsonify({"status": "completed"})
    if current_row is None:
        return jsonify({"status": "starting"})
    return jsonify(current_row)


@app.route("/api/simulation/status", methods=["GET"]) 
def simulation_status():
    total = len(simulation_data)
    return jsonify({
        "running": simulation_running,
        "index": simulation_index,
        "total": total,
        "current_row": current_row
    })


# --- Pump Control APIs ---
@app.route("/api/pump/on", methods=["POST"])
def pump_on():
    global last_pump_status
    last_pump_status = "ON"
    try:
        log_notification("Pump manually turned ON", "info")
    except Exception:
        pass
    return jsonify({"status": "Pump turned ON"})


@app.route("/api/pump/off", methods=["POST"])
def pump_off():
    global last_pump_status
    last_pump_status = "OFF"
    try:
        log_notification("Pump manually turned OFF", "info")
    except Exception:
        pass
    return jsonify({"status": "Pump turned OFF"})


# Simple hardware pump control endpoint for Pump Control page
@app.route("/api/hardware/pump", methods=["POST"]) 
def hardware_pump():
    data = request.get_json(silent=True) or {}
    action = str(data.get("action", "")).upper()
    if action not in ("ON", "OFF"):
        return jsonify({"error": "Invalid action"}), 400
    global last_pump_status
    last_pump_status = action
    try:
        log_notification(f"Pump manually turned {action}", "info")
    except Exception:
        pass
    return jsonify({"status": f"Pump {action}"})


# --- Data APIs ---
@app.route("/api/data/all", methods=["GET"])
def get_all_data():
    rows = fetch_all()
    result = [
        {"id": r[0], "timestamp": r[1], "soil_moisture": r[2],
         "temperature": r[3], "humidity": r[4], "pump_status": r[5]}
        for r in rows
    ]
    return jsonify(result)


@app.route("/api/data/recent", methods=["GET"]) 
def get_recent_data():
    """Return most recent N sensor_data rows"""
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        limit = 50
    rows = fetch_all()  # already ordered DESC
    rows = rows[:limit]
    result = [
        {"id": r[0], "timestamp": r[1], "soil_moisture": r[2],
         "temperature": r[3], "humidity": r[4], "pump_status": r[5]}
        for r in rows
    ]
    return jsonify(result)


# --- Mode APIs ---
@app.route("/api/mode", methods=["GET", "POST"])
def api_mode():
    global current_mode
    if request.method == "GET":
        return jsonify({"mode": current_mode})
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode", "")).lower()
    if mode not in ("simulation", "hardware"):
        return jsonify({"error": "Invalid mode"}), 400
    current_mode = mode
    # Stop simulation if switching to hardware
    if current_mode == "hardware":
        global simulation_running
        simulation_running = False
    return jsonify({"mode": current_mode})


@app.route("/api/sensors/latest", methods=["GET"])
def sensors_latest():
    import sqlite3
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "irrigation.db"))
    c = conn.cursor()
    c.execute("SELECT timestamp, soil_moisture, temperature, humidity, pump_status FROM sensor_data ORDER BY id DESC LIMIT 1")
    r = c.fetchone()
    conn.close()
    if not r:
        return jsonify({})
    return jsonify({
        "timestamp": r[0],
        "soil_moisture": r[1],
        "temperature": r[2],
        "humidity": r[3],
        "pump_status": r[4],
    })


# --- Water usage logging APIs ---
@app.route("/api/water/log", methods=["POST"])
def water_log():
    data = request.get_json()
    timestamp = data.get("timestamp")
    liters = data.get("liters_used")
    log_water_usage(timestamp, liters)
    return jsonify({"status": "logged"})


@app.route("/api/water/usage", methods=["GET"])
def water_usage():
    data = fetch_water_usage()
    usage_list = [{"timestamp": row[1], "liters_used": row[2]} for row in data]
    resp = jsonify(usage_list)
    # Prevent any caching so the page live-updates reliably
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


# --- Cross-page status API ---
@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "mode": current_mode,
        "simulation_running": simulation_running,
        "pump_status": last_pump_status,
        "water_used": float(fetch_water_usage_total()),
    })


# --- Notifications API ---
@app.route("/api/notifications", methods=["GET"])  
def api_notifications():
    try:
        rows = fetch_notifications(limit=int(request.args.get("limit", 10)))
    except Exception:
        rows = []
    return jsonify([
        {"id": r[0], "timestamp": r[1], "message": r[2], "type": r[3]} for r in rows
    ])


# --- Reports API ---
@app.route("/api/reports", methods=["GET"])
def api_reports():
    import sqlite3, io, csv
    from flask import Response
    range_key = request.args.get("range", "daily")
    export = request.args.get("export")  # 'csv' or 'pdf'
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "irrigation.db"))
    c = conn.cursor()
    # Determine grouping
    if range_key == "weekly":
        bucket = "%Y-%W"
    else:
        bucket = "%Y-%m-%d"
    c.execute(
        f"""
        SELECT strftime('{bucket}', timestamp) as bucket,
               AVG(soil_moisture), AVG(temperature), AVG(humidity)
        FROM sensor_data
        GROUP BY bucket
        ORDER BY bucket ASC
        """
    )
    sensor_rows = c.fetchall()
    c.execute(
        f"""
        SELECT strftime('{bucket}', timestamp) as bucket,
               SUM(liters_used)
        FROM water_usage
        GROUP BY bucket
        ORDER BY bucket ASC
        """
    )
    water_rows = c.fetchall()
    conn.close()

    # Merge by bucket
    water_map = {r[0]: (r[1] or 0) for r in water_rows}
    report = []
    for b, avg_m, avg_t, avg_h in sensor_rows:
        report.append({
            "bucket": b,
            "avg_soil_moisture": avg_m or 0,
            "avg_temperature": avg_t or 0,
            "avg_humidity": avg_h or 0,
            "total_liters": water_map.get(b, 0)
        })

    if export == "csv":
        si = io.StringIO()
        writer = csv.writer(si)
        writer.writerow(["bucket", "avg_soil_moisture", "avg_temperature", "avg_humidity", "total_liters"])
        for r in report:
            writer.writerow([r["bucket"], r["avg_soil_moisture"], r["avg_temperature"], r["avg_humidity"], r["total_liters"]])
        output = si.getvalue()
        return Response(output, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=report.csv'})

    if export == "pdf":
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            buf = io.BytesIO()
            cpdf = canvas.Canvas(buf, pagesize=letter)
            cpdf.setFont("Helvetica", 12)
            y = 750
            cpdf.drawString(50, y, "Smart Irrigation Report")
            y -= 30
            for r in report:
                line = f"{r['bucket']}: Moist {r['avg_soil_moisture']:.1f}, Temp {r['avg_temperature']:.1f}C, Hum {r['avg_humidity']:.1f}%, Liters {r['total_liters']:.1f}"
                cpdf.drawString(50, y, line)
                y -= 18
                if y < 50:
                    cpdf.showPage(); y = 750
            cpdf.save()
            pdf = buf.getvalue()
            buf.close()
            return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': 'attachment; filename=report.pdf'})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify(report)


# --- Settings API ---
@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify({
            "moisture_threshold": float(get_setting("moisture_threshold", "500") or 500),
            "auto_mode": (get_setting("auto_mode", "false") == "true"),
        })
    data = request.get_json(silent=True) or {}
    if "moisture_threshold" in data:
        set_setting("moisture_threshold", str(data.get("moisture_threshold")))
    if "auto_mode" in data:
        set_setting("auto_mode", "true" if data.get("auto_mode") else "false")
    return jsonify({"status": "saved"})


# --- System summary API ---
@app.route("/api/system/summary", methods=["GET"]) 
def api_system_summary():
    try:
        health = {"backend": "ok"}
        mode = current_mode
        status = {
            "health": health,
            "mode": mode,
            "simulation_running": simulation_running,
            "pump_status": last_pump_status,
            "water_used": float(fetch_water_usage_total()),
            "moisture_threshold": float(get_setting("moisture_threshold", "500") or 500),
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Metrics APIs (last 24 hours) ---
def _since_for_range(range_key: str) -> str:
    import datetime
    now = datetime.datetime.utcnow()
    if range_key == "24h":
        dt = now - datetime.timedelta(hours=24)
    elif range_key == "7d":
        dt = now - datetime.timedelta(days=7)
    elif range_key == "30d":
        dt = now - datetime.timedelta(days=30)
    elif range_key == "90d":
        dt = now - datetime.timedelta(days=90)
    else:
        dt = now - datetime.timedelta(hours=24)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@app.route("/api/metrics/water", methods=["GET"]) 
def metrics_water():
    import sqlite3
    range_key = request.args.get("range", "24h")
    since = _since_for_range(range_key)
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "irrigation.db"))
    c = conn.cursor()
    # Group by hour for 24h; by day for >=7d
    bucket = "%Y-%m-%d %H:00:00" if range_key == "24h" else "%Y-%m-%d"
    c.execute(
        f"""
        SELECT strftime('{bucket}', timestamp) as bucket,
               SUM(liters_used) as liters
        FROM water_usage
        WHERE timestamp >= ?
        GROUP BY bucket
        ORDER BY bucket ASC
        """,
        (since,)
    )
    rows = c.fetchall()
    conn.close()
    return jsonify([{"bucket": r[0], "liters": r[1] or 0} for r in rows])


@app.route("/api/metrics/sensors", methods=["GET"]) 
def metrics_sensors():
    import sqlite3
    range_key = request.args.get("range", "24h")
    since = _since_for_range(range_key)
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "irrigation.db"))
    c = conn.cursor()
    c.execute(
        """
        SELECT timestamp, soil_moisture, temperature, humidity
        FROM sensor_data
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
        """,
        (since,)
    )
    rows = c.fetchall()
    conn.close()
    return jsonify([
        {
            "timestamp": r[0],
            "soil_moisture": r[1],
            "temperature": r[2],
            "humidity": r[3],
        }
        for r in rows
    ])


@app.route("/api/metrics/summary", methods=["GET"]) 
def metrics_summary():
    """Aggregated stats for charts (min/avg/max and counts)."""
    import sqlite3
    range_key = request.args.get("range", "24h")
    since = _since_for_range(range_key)
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "irrigation.db"))
    c = conn.cursor()
    c.execute("SELECT COUNT(1), SUM(CASE WHEN pump_status IN ('ON',1) THEN 1 ELSE 0 END) FROM sensor_data WHERE timestamp >= ?", (since,))
    total_rows, pump_on = c.fetchone() or (0, 0)
    c.execute("SELECT MIN(soil_moisture), AVG(soil_moisture), MAX(soil_moisture) FROM sensor_data WHERE timestamp >= ?", (since,))
    moist_min, moist_avg, moist_max = c.fetchone() or (None, None, None)
    c.execute("SELECT SUM(liters_used) FROM water_usage WHERE timestamp >= ?", (since,))
    total_liters = c.fetchone()[0] or 0
    conn.close()
    return jsonify({
        "total_rows": total_rows or 0,
        "pump_on": pump_on or 0,
        "pump_off": (total_rows or 0) - (pump_on or 0),
        "moisture": {"min": moist_min, "avg": moist_avg, "max": moist_max},
        "total_liters": total_liters,
    })


# --- Serve frontend files ---
FRONTEND_FOLDER = os.path.join(os.path.dirname(__file__), "../frontend")

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_FOLDER, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # prevent overriding API routes
    if path.startswith("api/"):
        return jsonify({"error": "Invalid API path"}), 404
    return send_from_directory(FRONTEND_FOLDER, path)


if __name__ == "__main__":
    init_db()  # initialize DB on startup
    app.run(host="0.0.0.0", port=5000, debug=True)
