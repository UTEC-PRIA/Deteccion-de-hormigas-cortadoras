/* ═══════════════════════════════════════════════
   Drone Mission Control — Frontend Logic
   Wizard navigation, WebSocket telemetry, Leaflet map
   ═══════════════════════════════════════════════ */

// ── State ──────────────────────────────────────
let currentStep = 1;
let missionId = null;
let isSimulation = false;
let ws = null;
let map = null;
let droneMarker = null;
let flightPath = null;
let mapInitialized = false;

// ── Helpers ────────────────────────────────────
function $(id) { return document.getElementById(id); }

async function api(endpoint, method = 'POST', body = null) {
    const opts = { method };
    if (body) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(endpoint, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'API Error');
    return data;
}

function toast(message, type = 'info') {
    const container = $('toastContainer');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icons = { success: 'ri-check-line', error: 'ri-error-warning-line', info: 'ri-information-line', warning: 'ri-alert-line' };
    el.innerHTML = `<i class="${icons[type] || icons.info}"></i> ${message}`;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

function addLog(message, type = 'info') {
    const container = $('logContainer');
    if (!container) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="log-time">${time}</span>${message}`;
    container.prepend(entry);
    if (container.children.length > 100) container.lastChild.remove();
}

// ── Wizard Navigation ──────────────────────────
function goToStep(step) {
    if (step < 1 || step > 5) return;
    // Hide all panels
    document.querySelectorAll('.wizard-panel').forEach(p => { p.classList.remove('active'); });
    // Show target
    const panel = $(`panel-${step}`);
    if (panel) panel.classList.add('active');

    // Update stepper visual
    document.querySelectorAll('.step').forEach(s => {
        const sn = parseInt(s.dataset.step);
        s.classList.remove('active');
        if (sn < step) s.classList.add('done');
        if (sn === step) { s.classList.add('active'); s.classList.remove('done'); }
        if (sn > step) s.classList.remove('done');
    });
    document.querySelectorAll('.step-line').forEach(l => {
        const ln = parseInt(l.dataset.line);
        if (ln < step) l.classList.add('done');
        else l.classList.remove('done');
    });

    currentStep = step;

    // Trigger step-specific init
    if (step === 3) detectSerialPorts();
    if (step === 4) initMap();
}

// ── Step 1: Mission Config ─────────────────────
function updateDateTime() {
    $('inputDateTime').value = new Date().toLocaleString();
}

async function createMission() {
    const mode = $('selectCaptureMode').value;
    const interval = parseInt($('selectInterval').value);
    try {
        const res = await api('/api/mission/create', 'POST', { capture_mode: mode, capture_interval: interval });
        missionId = res.mission.mission_id;
        $('missionBadge').textContent = missionId;
        $('inputMissionId').value = missionId;
        toast(`Misión ${missionId} creada`, 'success');
        addLog(`Misión ${missionId} creada (modo: ${mode})`, 'success');
        goToStep(2);
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadPrevMissions() {
    try {
        const res = await api('/api/mission/list', 'GET');
        if (res.missions && res.missions.length > 0) {
            $('prevMissionsSection').style.display = 'block';
            const list = $('prevMissionsList');
            list.innerHTML = res.missions.slice(0, 5).map(m => `
                <div class="status-row">
                    <span class="status-label" style="flex:none; font-weight:600; color:var(--blue)">${m.mission_id}</span>
                    <span class="status-label">${m.capture_mode} — ${m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}</span>
                    <span class="status-value">${m.num_files || 0} archivos ${m.has_dataset ? '✅' : ''}</span>
                </div>
            `).join('');
        }
    } catch (e) { /* ignore */ }
}

// Show/hide interval based on capture mode
$('selectCaptureMode').addEventListener('change', function() {
    $('intervalGroup').style.display = this.value === 'photo' ? 'flex' : 'none';
});

// ── Step 2: GoPro ──────────────────────────────
async function connectGoProWireless() {
    toast('Buscando GoPro por BLE y conectando WiFi...', 'info');
    try {
        const res = await api('/api/gopro/connect', 'POST', { mode: 'wireless', simulation: false });
        showGoProConnected('BLE+WiFi');
        if (res.status && res.status.wifi_ssid) {
            $('dotWifiSaved').classList.add('green');
            $('goProWifiSsid').textContent = res.status.wifi_ssid;
        }
        toast('GoPro conectada inalámbricamente', 'success');
        addLog('GoPro conectada por BLE+WiFi', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function connectGoProDirect() {
    toast('Conectando a WiFi guardada de GoPro...', 'info');
    try {
        const res = await api('/api/gopro/connect', 'POST', { mode: 'wifi_direct', simulation: false });
        showGoProConnected('WiFi Directo');
        if (res.status && res.status.wifi_ssid) {
            $('dotWifiSaved').classList.add('green');
            $('goProWifiSsid').textContent = res.status.wifi_ssid;
        }
        toast('GoPro conectada por WiFi directo', 'success');
        addLog('GoPro conectada por WiFi directo', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function connectGoProSim() {
    try {
        await api('/api/gopro/connect', 'POST', { mode: 'simulation', simulation: true });
        isSimulation = true;
        $('simBadge').classList.add('active');
        showGoProConnected('Simulación');
        $('dotWifiSaved').classList.add('green');
        $('goProWifiSsid').textContent = 'Simulada';
        toast('GoPro en modo simulación', 'success');
        addLog('GoPro simulación activada', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

function showGoProConnected(mode) {
    $('goProStatusPanel').style.display = 'block';
    $('goProConnMode').textContent = mode;
    $('btnStartCapture').disabled = false;
    // hide action cards or mark them active
    document.querySelectorAll('#panel-2 .action-card').forEach(c => c.classList.remove('active'));
}

async function startCapture() {
    try {
        await api('/api/gopro/start_capture', 'POST');
        $('dotCapture').classList.add('green', 'pulse');
        $('goProCaptureStatus').textContent = 'Activa';
        $('btnStartCapture').disabled = true;
        toast('Captura iniciada en GoPro', 'success');
        addLog('Captura iniciada en la GoPro', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

// ── Step 3: Telemetry ──────────────────────────
async function detectSerialPorts() {
    try {
        const res = await api('/api/telemetry/ports', 'GET');
        const sel = $('selectPort');
        if (res.ports && res.ports.length > 0) {
            sel.innerHTML = res.ports.map(p =>
                `<option value="${p.device}">${p.device} ${p.description ? '(' + p.description + ')' : ''}</option>`
            ).join('');
        }
    } catch (e) { /* keep defaults */ }
}

async function connectTelemetry() {
    const port = $('selectPort').value;
    const baud = parseInt($('selectBaud').value);
    toast('Conectando telemetría MAVLink...', 'info');
    try {
        await api('/api/telemetry/connect', 'POST', { port, baudrate: baud, simulation: false });
        showTelemConnected('Serial');
        toast('Telemetría conectada', 'success');
        addLog(`Telemetría conectada en ${port}`, 'success');
        startWebSocket();
    } catch (e) { toast(e.message, 'error'); }
}

async function connectTelemetrySim() {
    try {
        await api('/api/telemetry/connect', 'POST', { port: '', baudrate: 57600, simulation: true });
        isSimulation = true;
        $('simBadge').classList.add('active');
        showTelemConnected('Simulación');
        toast('Telemetría en simulación', 'success');
        addLog('Telemetría simulación activada', 'success');
        startWebSocket();
    } catch (e) { toast(e.message, 'error'); }
}

function showTelemConnected(mode) {
    $('telemStatusPanel').style.display = 'block';
    $('telemConnMode').textContent = mode;
    $('btnConnectTelem').disabled = true;
    $('btnTelemSim').disabled = true;
}

// ── Step 4: Flight + Map ───────────────────────
function initMap() {
    if (mapInitialized) return;
    mapInitialized = true;

    map = L.map('mapContainer', {
        center: [-30.9000, -55.5500],
        zoom: 16,
        zoomControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 19,
    }).addTo(map);

    // Drone marker (custom icon)
    const droneIcon = L.divIcon({
        html: '<div style="font-size:24px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5))">🛩️</div>',
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        className: '',
    });
    droneMarker = L.marker([-30.9000, -55.5500], { icon: droneIcon }).addTo(map);

    // Flight trace polyline
    flightPath = L.polyline([], {
        color: '#3b82f6', weight: 3, opacity: 0.8,
        dashArray: '8 4',
    }).addTo(map);

    // Force map resize
    setTimeout(() => map.invalidateSize(), 200);
}

function updateMap(data, trace) {
    if (!map || !droneMarker) return;
    const lat = data.lat;
    const lon = data.lon;
    if (lat === 0 && lon === 0) return;

    droneMarker.setLatLng([lat, lon]);

    if (trace && trace.length > 0) {
        const latlngs = trace.map(t => [t.lat, t.lon]);
        flightPath.setLatLngs(latlngs);

        // Auto-center map on drone
        if (trace.length <= 5) {
            map.setView([lat, lon], 16);
        }
    }
}

function updateTelemetryUI(data, flightState, missionState) {
    $('valAlt').innerHTML = `${Math.round(data.relative_alt || 0)}<span class="telemetry-unit">m</span>`;
    $('valSpeed').innerHTML = `${(data.speed || 0).toFixed(1)}<span class="telemetry-unit">m/s</span>`;
    $('valBat').innerHTML = `${data.battery_percent >= 0 ? data.battery_percent : '—'}<span class="telemetry-unit">%</span>`;
    $('valHdg').innerHTML = `${Math.round(data.heading || 0)}<span class="telemetry-unit">°</span>`;
    $('valSat').textContent = data.satellites || 0;
    $('valFix').textContent = data.gps_fix >= 3 ? '3D Fix' : data.gps_fix >= 2 ? '2D' : 'No Fix';

    // Flight mode badge
    const badge = $('flightModeBadge');
    const mode = data.flight_mode || 'UNKNOWN';
    badge.textContent = `${mode}${data.armed ? ' ● ARMED' : ''}`;
    badge.className = 'flight-mode-badge';
    if (data.armed) badge.classList.add('armed');
    if (['RTL', 'LAND'].includes(mode)) badge.classList.add('danger');

    // GPS dot
    const dotGps = $('dotGps');
    if (dotGps) {
        dotGps.className = 'status-dot ' + (data.gps_fix >= 3 ? 'green' : data.gps_fix >= 2 ? 'amber' : 'red');
        $('telemGps').textContent = data.gps_fix >= 3 ? `3D Fix (${data.satellites} sat)` : 'Buscando...';
    }

    // Arm dot
    const dotArm = $('dotArm');
    if (dotArm) {
        dotArm.className = 'status-dot ' + (data.armed ? 'green pulse' : '');
        $('telemArm').textContent = data.armed ? 'ARMED' : 'DISARMED';
    }

    // GoPro capture indicator in flight
    const dotGp = $('dotGoproFlight');
    if (dotGp) {
        const capActive = document.querySelector('#goProCaptureStatus');
        const isCapturing = capActive && capActive.textContent === 'Activa';
        dotGp.className = 'status-dot ' + (isCapturing ? 'green pulse' : '');
        $('goproFlightStatus').textContent = isCapturing ? 'Capturando' : 'Inactiva';
    }

    // Landing detection
    if (flightState === 'LANDED' || flightState === 'LANDING') {
        $('landingAlert').classList.add('show');
    }
}

// ── WebSocket ──────────────────────────────────
function startWebSocket() {
    if (ws) ws.close();
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/telemetry`);

    ws.onopen = () => addLog('WebSocket conectado', 'success');
    ws.onclose = () => {
        addLog('WebSocket desconectado', 'warning');
        setTimeout(() => { if (currentStep === 4) startWebSocket(); }, 3000);
    };
    ws.onerror = () => addLog('Error en WebSocket', 'error');

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'telemetry') {
            updateTelemetryUI(msg.data, msg.flight_state, msg.mission_state);
            updateMap(msg.data, msg.trace);
        }
    };
}

// ── Step 5: Download & Results ─────────────────
async function connectGoProBleDownload() {
    toast('Buscando GoPro por BLE...', 'info');
    try {
        await api('/api/gopro/connect', 'POST', { mode: 'wireless', simulation: isSimulation });
        toast('GoPro conectada para descarga', 'success');
        startDownload();
    } catch (e) { toast(e.message, 'error'); }
}

async function connectGoProWifiDownload() {
    toast('Conectando a WiFi de GoPro...', 'info');
    try {
        await api('/api/gopro/connect', 'POST', { mode: 'wifi_direct', simulation: isSimulation });
        toast('GoPro conectada por WiFi directo', 'success');
        startDownload();
    } catch (e) { toast(e.message, 'error'); }
}

async function startDownload() {
    $('downloadConnectPanel').style.display = 'none';
    $('downloadProgressPanel').style.display = 'block';
    addLog('Iniciando descarga de media...', 'info');

    try {
        // Poll progress
        const progressPoll = setInterval(async () => {
            try {
                const prog = await api('/api/download/progress', 'GET');
                $('downloadPercent').textContent = `${prog.percent || 0}%`;
                $('downloadFill').style.width = `${prog.percent || 0}%`;
                $('downloadDetail').textContent = prog.filename ? `Descargando: ${prog.filename}` : 'Preparando...';
            } catch (e) { /* ignore */ }
        }, 500);

        const res = await api('/api/download/start', 'POST');
        clearInterval(progressPoll);

        $('downloadPercent').textContent = '100%';
        $('downloadFill').style.width = '100%';
        $('downloadDetail').textContent = `${res.downloaded || 0} archivos descargados`;

        toast(`Descarga completa: ${res.downloaded} archivos`, 'success');
        addLog(`Descarga completa: ${res.downloaded} archivos`, 'success');

        $('syncPanel').style.display = 'block';
    } catch (e) {
        toast(e.message, 'error');
        addLog(`Error en descarga: ${e.message}`, 'error');
    }
}

async function generateDataset() {
    toast('Generando dataset geoposicionado...', 'info');
    $('btnSync').disabled = true;
    try {
        const res = await api('/api/sync/generate', 'POST');
        toast(`Dataset generado: ${res.entries} entradas`, 'success');
        addLog(`Dataset generado: ${res.entries} entradas`, 'success');

        // Show results
        $('syncPanel').style.display = 'none';
        $('resultsPanel').style.display = 'block';
        $('sumPhotos').textContent = res.entries || 0;
        $('sumMatched').textContent = res.entries || 0;
        $('sumMission').textContent = missionId || '—';

        // Fill table
        if (res.dataset) {
            const tbody = $('datasetBody');
            tbody.innerHTML = res.dataset.map(row => `
                <tr>
                    <td>${row.image}</td>
                    <td>${row.image_timestamp ? new Date(row.image_timestamp).toLocaleTimeString() : '—'}</td>
                    <td>${parseFloat(row.lat).toFixed(6)}</td>
                    <td>${parseFloat(row.lon).toFixed(6)}</td>
                    <td>${parseFloat(row.alt).toFixed(1)}</td>
                    <td>${row.heading}°</td>
                    <td>${row.time_diff_ms}</td>
                </tr>
            `).join('');
        }

        // Mark step 5 as done
        document.querySelector('[data-step="5"]').classList.add('done');
    } catch (e) {
        toast(e.message, 'error');
        $('btnSync').disabled = false;
    }
}

function downloadDatasetCsv() {
    if (missionId) {
        window.open(`/api/dataset/${missionId}`, '_blank');
    }
}

// ── Quick Simulation ───────────────────────────
async function startSimulation() {
    toast('Iniciando simulación completa...', 'info');
    try {
        const res = await api('/api/simulation/start', 'POST');
        isSimulation = true;
        missionId = res.mission.mission_id;
        $('missionBadge').textContent = missionId;
        $('simBadge').classList.add('active');

        // Update step 2 UI
        showGoProConnected('Simulación');
        $('dotCapture').classList.add('green', 'pulse');
        $('goProCaptureStatus').textContent = 'Activa';

        // Jump to step 4
        showTelemConnected('Simulación');
        goToStep(4);
        startWebSocket();
        toast('Simulación iniciada — observa el vuelo en el mapa', 'success');
        addLog('Simulación completa iniciada', 'success');
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ── Reset ──────────────────────────────────────
async function resetMission() {
    try {
        await api('/api/mission/reset', 'POST');
        if (ws) ws.close();
        ws = null;
        missionId = null;
        isSimulation = false;
        mapInitialized = false;
        map = null;

        $('missionBadge').textContent = 'Sin misión';
        $('simBadge').classList.remove('active');
        $('goProStatusPanel').style.display = 'none';
        $('telemStatusPanel').style.display = 'none';
        $('btnStartCapture').disabled = true;
        $('btnConnectTelem').disabled = false;
        $('btnTelemSim').disabled = false;
        $('landingAlert').classList.remove('show');
        $('downloadConnectPanel').style.display = 'block';
        $('downloadProgressPanel').style.display = 'none';
        $('syncPanel').style.display = 'none';
        $('resultsPanel').style.display = 'none';
        $('cardGoProUsb').classList.remove('active');
        $('logContainer').innerHTML = '';
        $('mapContainer').innerHTML = '';

        document.querySelectorAll('.step').forEach(s => s.classList.remove('done'));
        goToStep(1);
        toast('Misión reiniciada', 'info');
    } catch (e) { toast(e.message, 'error'); }
}

// ── Init ───────────────────────────────────────
updateDateTime();
setInterval(updateDateTime, 1000);
loadPrevMissions();
