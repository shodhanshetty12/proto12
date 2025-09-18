let simulationRunning = false;
let simulationInterval;
let waterUsed = 0;
let pumpStatus = "OFF";
let autoMode = false; // Automatic pump toggle

// DOM Elements
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const tableBody = document.getElementById("simulationTableBody");
const pumpStatusEl = document.getElementById("pumpStatus");
const waterUsageEl = document.getElementById("waterUsage");
const autoModeToggle = document.getElementById("autoModeToggle");
const statusEl = document.getElementById("status");
const autoScrollToggle = document.getElementById("autoScrollToggle");

/* ------------------- UI Update Functions ------------------- */
function updatePumpStatus(status) {
  pumpStatus = status;
  if (!pumpStatusEl) return;
  pumpStatusEl.textContent = `Pump Status: ${status}`;
  pumpStatusEl.style.color = status === "ON" ? "green" : "red";
}

function updateWaterUsage(amount) {
  waterUsed += amount;
  if (waterUsageEl) {
    waterUsageEl.textContent = `Water Used: ${waterUsed} L`;
  }
}

/* ------------------- Simulation Logic ------------------- */
async function fetchSimulationData() {
  try {
    const response = await fetch("/api/simulation/data");
    const data = await response.json();

    // Handle simulation status responses
    if (data.status === "stopped") {
      statusEl.textContent = "Simulation stopped.";
      clearInterval(simulationInterval);
      simulationRunning = false;
      return;
    }
    if (data.status === "completed") {
      statusEl.textContent = "Simulation completed.";
      clearInterval(simulationInterval);
      simulationRunning = false;
      return;
    }
    if (data.status === "starting") {
      statusEl.textContent = "Simulation starting...";
      return;
    }

    // Insert row into table
    if (tableBody) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${data.timestamp}</td>
        <td>${data.soil_moisture}</td>
        <td>${data.temperature}</td>
        <td>${data.humidity}</td>
      `;
      tableBody.appendChild(row);
      if (!autoScrollToggle || autoScrollToggle.checked) {
        row.scrollIntoView({ behavior: "smooth", block: "end" });
      }
    }

    // Pump control
    if (autoMode) {
      if (data.pump_status === 1 || data.soil_moisture < 400) {
        updatePumpStatus("ON");
        updateWaterUsage(2);
      } else {
        updatePumpStatus("OFF");
      }
    } else {
      // Respect backend pump_status when not in auto mode
      updatePumpStatus(data.pump_status === 1 ? "ON" : "OFF");
      if (data.pump_status === 1) updateWaterUsage(2);
    }
  } catch (error) {
    console.error("Error fetching simulation data:", error);
  }
}

/* ------------------- Button Handlers ------------------- */
if (startBtn) {
  startBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/simulation/start", { method: "POST" });
      const result = await res.json();
      if (result.status === "started") {
        statusEl.textContent = "Simulation started.";
        simulationRunning = true;
        waterUsed = 0;
        updateWaterUsage(0);
        if (tableBody) tableBody.innerHTML = "";
        simulationInterval = setInterval(fetchSimulationData, 1000);
      }
    } catch (error) {
      statusEl.textContent = "Failed to start simulation.";
      console.error("Failed to start simulation:", error);
    }
  });
}

if (stopBtn) {
  stopBtn.addEventListener("click", async () => {
    try {
      await fetch("/api/simulation/stop", { method: "POST" });
      statusEl.textContent = "Simulation stopped.";
    } catch (error) {
      statusEl.textContent = "Failed to stop simulation.";
      console.error("Failed to stop simulation:", error);
    }
    simulationRunning = false;
    clearInterval(simulationInterval);
    updatePumpStatus("OFF");
  });
}

if (autoModeToggle) {
  autoModeToggle.addEventListener("change", () => {
    autoMode = autoModeToggle.checked;
  });
}

if (autoScrollToggle) {
  autoScrollToggle.addEventListener("change", () => {
    // no-op; checkbox state is read during updates
  });
}

/* ------------------- Initialization on Load ------------------- */
async function initializeFromBackend() {
  try {
    // Cross-page status
    try {
      const st = await fetch('/api/status');
      const sj = await st.json();
      if (sj && sj.pump_status) {
        updatePumpStatus((sj.pump_status || 'OFF').toUpperCase());
      }
      if (waterUsageEl && typeof sj.water_used === 'number') {
        waterUsed = 0;
        updateWaterUsage(Number(sj.water_used || 0));
      }
    } catch {}
    // Initialize table with recent data if exists
    if (tableBody) {
      const res = await fetch("/api/data/recent?limit=50");
      const rows = await res.json();
      tableBody.innerHTML = "";
      rows.reverse().forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${r.timestamp}</td>
          <td>${r.soil_moisture}</td>
          <td>${r.temperature}</td>
          <td>${r.humidity}</td>
        `;
        tableBody.appendChild(tr);
      });
      if (rows.length > 0) {
        const last = rows[0];
        updatePumpStatus(last.pump_status === 1 || last.pump_status === "ON" ? "ON" : "OFF");
      }
    }

    // Initialize water total from water usage logs
    if (waterUsageEl) {
      const usageRes = await fetch("/api/water/usage");
      const usageData = await usageRes.json();
      const total = usageData.reduce((sum, r) => sum + Number(r.liters_used || 0), 0);
      waterUsed = 0; // reset internal counter
      updateWaterUsage(total);
    }
  } catch (e) {
    console.error("Failed to initialize dashboard:", e);
  }
}

async function resumeIfRunning() {
  try {
    const res = await fetch("/api/simulation/status");
    const s = await res.json();
    if (s.running) {
      simulationRunning = true;
      statusEl && (statusEl.textContent = "Simulation running...");
      if (simulationInterval) clearInterval(simulationInterval);
      simulationInterval = setInterval(fetchSimulationData, 1000);
    }
  } catch (e) {
    // ignore
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initializeFromBackend();
  resumeIfRunning();
  // keep status in sync across pages
  setInterval(async ()=>{
    try { const r = await fetch('/api/status'); const j = await r.json(); if (j && j.pump_status) updatePumpStatus((j.pump_status||'OFF').toUpperCase()); if (waterUsageEl && typeof j.water_used==='number') { waterUsed = 0; updateWaterUsage(Number(j.water_used||0)); } } catch {}
  }, 5000);
});
