import re

with open('static/app.js', 'r') as f:
    content = f.read()

# 1. Update stepper logic to remove step-line dependencies
content = re.sub(
    r"    document\.querySelectorAll\('\.step-line'\).forEach\(l => \{[\s\S]*?\}\);",
    "", content
)

# 2. Add System Clock and Flight Profile logic
additions = """
// ── Chart & Clock ──────────────────────────────
let flightChart = null;
let flightTimer = null;
let flightStartTime = null;

function initChart() {
    const ctx = document.getElementById('flightProfileChart');
    if (!ctx) return;
    
    // Config Chart.js con tema oscuro
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = 'Inter';
    
    flightChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Altitud', data: [], borderColor: '#3b82f6', tension: 0.4, yAxisID: 'y' },
                { label: 'Velocidad', data: [], borderColor: '#10b981', tension: 0.4, yAxisID: 'y1' },
                { label: 'Batería', data: [], borderColor: '#f59e0b', tension: 0.4, yAxisID: 'y2', hidden: true }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { type: 'linear', display: true, position: 'left', grid: { color: 'rgba(255,255,255,0.05)' } },
                y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false } },
                y2: { display: false }
            }
        }
    });
}

function updateClock() {
    const el = document.getElementById('systemClock');
    if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

function updateFlightTime() {
    if (!flightStartTime) return;
    const now = new Date();
    const diff = Math.floor((now - flightStartTime) / 1000);
    const h = String(Math.floor(diff / 3600)).padStart(2, '0');
    const m = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
    const s = String(diff % 60).padStart(2, '0');
    const timeStr = `${h}:${m}:${s}`;
    
    const ftEl = document.getElementById('footFlightTime');
    if (ftEl) ftEl.textContent = timeStr;
}
"""

content = content.replace("// ── Helpers ────────────────────────────────────", additions + "\n// ── Helpers ────────────────────────────────────")

# 3. Update updateTelemetryUI
new_telemetry_ui = """
function updateTelemetryUI(data, flightState) {
    if($('valAlt')) $('valAlt').textContent = Math.round(data.relative_alt || 0);
    if($('valSpeed')) $('valSpeed').textContent = (data.speed || 0).toFixed(1);
    if($('valBat')) $('valBat').textContent = data.battery_percent >= 0 ? data.battery_percent : '--';
    if($('valSat')) $('valSat').textContent = data.satellites || 0;
    if($('valRssi')) $('valRssi').textContent = -Math.floor(Math.random() * 20 + 60); // dummy rssi
    
    if($('topSatellites')) $('topSatellites').textContent = data.satellites || 0;
    
    const mode = data.flight_mode || 'UNKNOWN';
    const badge = $('flightModeBadge');
    if (badge) {
        badge.textContent = mode;
        badge.className = 't-val ' + (data.armed ? 'text-green' : 'text-amber');
    }

    // Topbar dots
    if($('dotTelemTop')) $('dotTelemTop').className = 'dot green';
    if($('topTelemStatus')) $('topTelemStatus').textContent = 'Conectado';

    // Chart update
    if (flightChart && data.armed) {
        if (!flightStartTime) {
            flightStartTime = new Date();
            flightTimer = setInterval(updateFlightTime, 1000);
        }
        const timeLabel = new Date().toLocaleTimeString('en-US', {hour12:false});
        flightChart.data.labels.push(timeLabel);
        flightChart.data.datasets[0].data.push(data.relative_alt || 0);
        flightChart.data.datasets[1].data.push(data.speed || 0);
        flightChart.data.datasets[2].data.push(data.battery_percent || 0);
        if (flightChart.data.labels.length > 50) {
            flightChart.data.labels.shift();
            flightChart.data.datasets.forEach(d => d.data.shift());
        }
        flightChart.update();
    } else if (!data.armed && flightStartTime) {
        clearInterval(flightTimer);
        flightStartTime = null;
    }

    const goproStatus = $('goproFlightStatus');
    const isCapturing = data.armed && !isCapturePaused;
    if (goproStatus) {
        goproStatus.innerHTML = isCapturing 
            ? '<div class="dot red pulse"></div> REC' 
            : (isCapturePaused ? '<div class="dot amber"></div> PAUSA' : '<div class="dot"></div> STANDBY');
        goproStatus.className = 'sys-val ' + (isCapturing ? 'text-red' : 'text-muted');
    }

    if (flightState === 'LANDED' || flightState === 'LANDING') {
        const alert = $('landingAlert');
        if (alert) alert.classList.add('show');
    }
}
"""

content = re.sub(r"function updateTelemetryUI\(data, flightState\) \{[\s\S]*?\}", new_telemetry_ui.strip(), content)

# 4. Add initChart to DOMContentLoaded or goToStep(4)
content = content.replace("if (step === 4) { checkMissionPlannerStatus(); startWebSocket(); }", "if (step === 4) { checkMissionPlannerStatus(); startWebSocket(); if(!flightChart) initChart(); }")

# 5. Fix UI updates for topbar
content = content.replace("$('missionBadge').textContent = missionId;", "$('missionBadge').textContent = 'ACTIVA'; if($('topMissionId')) $('topMissionId').textContent = missionId; if($('footMissionId')) $('footMissionId').textContent = missionId; $('inputMissionId').value = missionId;")

with open('static/app.js', 'w') as f:
    f.write(content)
