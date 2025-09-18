# backend/hardware.py
from flask import Blueprint, request, jsonify
import datetime

hardware_bp = Blueprint("hardware", __name__)

# Store latest sensor data
latest_data = {
    "timestamp": None,
    "soil_moisture": None,
    "temperature": None,
    "humidity": None,
    "pump_status": "OFF"
}

# Endpoint 1: Receive sensor data (from NodeMCU later, now just test via POST)
@hardware_bp.route("/api/hardware/read", methods=["POST"])
def read_sensor():
    data = request.json
    latest_data["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    latest_data["soil_moisture"] = data.get("soil_moisture")
    latest_data["temperature"] = data.get("temperature")
    latest_data["humidity"] = data.get("humidity")

    # Auto pump logic (same rule: <400 moisture → ON)
    if latest_data["soil_moisture"] is not None and latest_data["soil_moisture"] < 400:
        latest_data["pump_status"] = "ON"
    else:
        latest_data["pump_status"] = "OFF"

    return jsonify({"status": "received", "data": latest_data})

# Endpoint 2: Get latest status
@hardware_bp.route("/api/hardware/status", methods=["GET"])
def get_status():
    return jsonify(latest_data)

# Endpoint 3: Manually toggle pump
@hardware_bp.route("/api/hardware/pump", methods=["POST"])
def control_pump():
    action = request.json.get("action")  # "ON" or "OFF"
    latest_data["pump_status"] = action
    return jsonify({"status": "pump updated", "pump_status": action})
