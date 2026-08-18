/* ═══════════════════════════════════════════════
   Drone Mission Control — Frontend Logic
   ═══════════════════════════════════════════════ */

// ── State ──────────────────────────────────────
let currentStep = 1;
let missionId = null;
let isSimulation = false;
let ws = null;
let selectedCaptureMode = null; // 'video' or 'photo'
let isCapturePaused = false;

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

function setLoading(btnId, loading, text = null) {
    const btn = $(btnId);
    if (!btn) return;
    btn.disabled = loading;
    if (text) btn.innerHTML = loading
        ? `<i class="ri-loader-4-line" style="animation:spin 1s linear infinite"></i> ${text}`
        : text;
}

// ── Wizard Navigation ──────────────────────────
function goToStep(step) {
    if (step < 1 || step > 5) return;
    document.querySelectorAll('.wizard-panel').forEach(p => { p.classList.remove('active'); });
    const panel = $(`panel-${step}`);
    if (panel) panel.classList.add('active');

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
    if (step === 3) { detectSerialPorts(); checkMAVProxyStatus(); }
    if (step === 4) { checkMissionPlannerStatus(); startWebSocket(); }
}

// ── Step 1: Mission Config ─────────────────────
function updateDateTime() {
    const el = $('inputDateTime');
    if (el) el.value = new Date().toLocaleString();
}

async function createMission() {
    try {
        setLoading('btnCreateMission', true, 'Creando...');
        const res = await api('/api/mission/create', 'POST', { capture_mode: 'photo', capture_interval: 2 });
        missionId = res.mission.mission_id;
        $('missionBadge').textContent = missionId;
        $('inputMissionId').value = missionId;
        toast(`Misión ${missionId} creada`, 'success');
        goToStep(2);
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        setLoading('btnCreateMission', false, '<i class="ri-add-circle-line"></i> Crear Misión');
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

// ── Step 2: GoPro ──────────────────────────────
async function connectGoProAuto() {
    const ssid = $('inputManualSsid').value.trim();
    const password = $('inputManualPassword').value.trim();
    if (!ssid || !password) {
        toast('Por favor ingresa el SSID y la Contraseña', 'warning');
        return;
    }
    setLoading('btnGoProAutoConnect', true, 'Conectando... (puede tardar ~20s)');
    toast(`Despertando GoPro y conectando a: ${ssid}...`, 'info');
    try {
        const res = await api('/api/gopro/connect', 'POST', { mode: 'auto', simulation: false, ssid, password });
        showGoProConnected('Auto (BLE+WiFi)', ssid);
        toast('✅ GoPro conectada exitosamente', 'success');
        addLog(`GoPro conectada a ${ssid}`, 'success');
    } catch (e) {
        toast(`Error: ${e.message}`, 'error');
        addLog(`Error conectando GoPro: ${e.message}`, 'error');
    } finally {
        setLoading('btnGoProAutoConnect', false, '<i class="ri-bluetooth-connect-line"></i> Conectar (Auto BLE + WiFi)');
    }
}

async function connectGoProSim() {
    try {
        await api('/api/gopro/connect', 'POST', { mode: 'simulation', simulation: true });
        isSimulation = true;
        $('simBadge').classList.add('active');
        showGoProConnected('Simulación', 'GP-SIM');
        toast('GoPro en modo simulación', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

function showGoProConnected(mode, ssid) {
    $('goProStatusPanel').style.display = 'block';
    $('goProConnMode').textContent = mode;
    if (ssid) $('goProWifiSsid').textContent = `(${ssid})`;
}

function selectCaptureMode(mode) {
    selectedCaptureMode = mode;
    // Update card highlight
    document.querySelectorAll('#panel-2 .action-card').forEach(c => c.style.borderColor = 'transparent');
    const card = mode === 'video' ? $('cardModeVideo') : $('cardModePhoto');
    if (card) card.style.borderColor = mode === 'video' ? 'var(--red, #ef4444)' : 'var(--blue)';

    // Show interval picker only for photo
    const intervalRow = $('photoIntervalRow');
    if (intervalRow) intervalRow.style.display = mode === 'photo' ? 'flex' : 'none';

    // Auto-start capture
    startCaptureWithMode(mode);
}

async function startCaptureWithMode(mode) {
    const interval = parseInt($('selectCaptureInterval')?.value || '2');
    toast(`Iniciando captura: ${mode === 'video' ? '🎬 Video' : '📷 Fotos'}...`, 'info');
    try {
        await api('/api/gopro/start_capture', 'POST', { mode, interval });
        $('captureActiveRow').style.display = 'flex';
        $('dotCapture').className = 'status-dot green pulse';
        $('goProCaptureStatus').textContent = mode === 'video' ? '🎬 Grabando video' : `📷 Timelapse (${interval}s)`;
        
        // Handle pause/stop buttons
        $('btnPauseCapture').style.display = 'inline-flex';
        $('btnPauseCapture').innerHTML = '<i class="ri-pause-circle-line"></i> Pausar';
        $('btnFlightPause').style.display = 'inline-flex';
        $('btnFlightPause').innerHTML = '<i class="ri-pause-circle-line"></i> Pausar Video';
        $('btnFlightStop').style.display = 'inline-flex';
        
        isCapturePaused = false;
        toast(`Captura iniciada: ${mode}`, 'success');
        addLog(`GoPro captura: ${mode}`, 'success');
    } catch (e) { toast(e.message, 'error'); }
}

async function stopCapture() {
    try {
        await api('/api/gopro/stop_capture', 'POST');
        $('dotCapture').className = 'status-dot';
        $('goProCaptureStatus').textContent = 'Detenida';
        $('captureActiveRow').style.display = 'none';
        $('btnFlightPause').style.display = 'none';
        $('btnFlightStop').style.display = 'none';
        selectedCaptureMode = null;
        isCapturePaused = false;
        document.querySelectorAll('#panel-2 .action-card').forEach(c => c.style.borderColor = 'transparent');
        toast('Captura detenida', 'info');
    } catch (e) { toast(e.message, 'error'); }
}

// ── Capture Pause/Resume ───────────────────────
async function pauseCapture() {
    if (!selectedCaptureMode) return;
    
    if (isCapturePaused) {
        // Resume
        toast('Reanudando captura...', 'info');
        try {
            const interval = parseInt($('selectCaptureInterval')?.value || '2');
            await api('/api/gopro/start_capture', 'POST', { mode: selectedCaptureMode, interval });
            isCapturePaused = false;
            
            $('dotCapture').className = 'status-dot green pulse';
            $('goProCaptureStatus').textContent = selectedCaptureMode === 'video' ? '🎬 Grabando video' : `📷 Timelapse`;
            
            $('btnPauseCapture').innerHTML = '<i class="ri-pause-circle-line"></i> Pausar';
            $('btnFlightPause').innerHTML = '<i class="ri-pause-circle-line"></i> Pausar Video';
            
            toast('Captura reanudada', 'success');
            addLog('Captura reanudada', 'success');
        } catch (e) { toast(e.message, 'error'); }
    } else {
        // Pause
        toast('Pausando captura...', 'info');
        try {
            await api('/api/gopro/stop_capture', 'POST');
            isCapturePaused = true;
            
            $('dotCapture').className = 'status-dot amber pulse';
            $('goProCaptureStatus').textContent = '⏸️ Pausado';
            
            $('btnPauseCapture').innerHTML = '<i class="ri-play-circle-line"></i> Reanudar';
            $('btnFlightPause').innerHTML = '<i class="ri-play-circle-line"></i> Reanudar Video';
            
            toast('Captura pausada', 'warning');
            addLog('Captura pausada', 'warning');
        } catch (e) { toast(e.message, 'error'); }
    }
}

// ── Step 3: Telemetry ──────────────────────────
async function detectSerialPorts() {
    try {
        const res = await api('/api/telemetry/ports', 'GET');
        const sel = $('selectPort');
        if (res.ports && res.ports.length > 0 && sel) {
            const tcpOption = '<option value="tcp:localhost:5761">TCP MAVProxy :5761</option>';
            sel.innerHTML = res.ports.map(p =>
                `<option value="${p.device}">${p.device} ${p.description ? '(' + p.description + ')' : ''}</option>`
            ).join('') + tcpOption;
        }
    } catch (e) { /* keep defaults */ }
}

async function checkMAVProxyStatus() {
    try {
        const res = await api('/api/mavproxy/status', 'GET');
        updateMAVProxyUI(res);
    } catch (e) { /* ignore */ }
}

function updateMAVProxyUI(status) {
    const dot = $('dotMAVProxy');
    const text = $('mavproxyStatusText');
    if (!dot || !text) return;
    if (status.running) {
        dot.className = 'status-dot green pulse';
        text.textContent = `Activo (${status.port} @ ${status.baudrate})`;
        text.style.color = 'var(--green)';
    } else {
        dot.className = 'status-dot';
        text.textContent = 'Inactivo';
        text.style.color = '';
    }
}

async function autoConnectTelemetry() {
    toast('Escaneando puertos y baudrates MAVLink...', 'info');
    setLoading('btnConnectTelem', true, 'Escaneando...');
    try {
        const res = await api('/api/telemetry/auto_connect', 'POST', {});
        showTelemConnected('Auto Serial');
        toast('✅ Telemetría conectada automáticamente', 'success');
        addLog(`Telemetría autodetectada`, 'success');
        startWebSocket();
        
        // Auto-advance and launch Mission Planner
        setTimeout(() => {
            goToStep(4);
            launchMissionPlanner();
        }, 1000);
    } catch (e) {
        toast(`Error: ${e.message}`, 'error');
    } finally {
        setLoading('btnConnectTelem', false, '<i class="ri-radar-line"></i> Autodetectar y Conectar');
    }
}

async function connectTelemetry() {
    const port = $('selectPort').value;
    const baud = parseInt($('selectBaud').value);
    toast('Conectando telemetría MAVLink...', 'info');
    try {
        await api('/api/telemetry/connect', 'POST', { port, baudrate: baud, simulation: false });
        showTelemConnected(port.startsWith('tcp') ? 'TCP MAVProxy' : 'Serial');
        toast('Telemetría conectada', 'success');
        startWebSocket();
        
        // Auto-advance and launch Mission Planner
        setTimeout(() => {
            goToStep(4);
            launchMissionPlanner();
        }, 1000);
    } catch (e) { toast(e.message, 'error'); }
}

async function connectTelemetrySim() {
    try {
        await api('/api/telemetry/connect', 'POST', { port: '', baudrate: 57600, simulation: true });
        isSimulation = true;
        $('simBadge').classList.add('active');
        showTelemConnected('Simulación');
        toast('Telemetría en simulación', 'success');
        startWebSocket();
    } catch (e) { toast(e.message, 'error'); }
}

function showTelemConnected(mode) {
    const panel = $('telemStatusPanel');
    if (panel) panel.style.display = 'block';
    const modeEl = $('telemConnMode');
    if (modeEl) modeEl.textContent = mode;
    setLoading('btnConnectTelem', false, '<i class="ri-radar-line"></i> Autodetectar y Conectar');
    const btnSim = $('btnTelemSim');
    if (btnSim) btnSim.disabled = true;
}

// ── Step 4: Mission Planner ────────────────────
async function checkMissionPlannerStatus() {
    try {
        const res = await api('/api/mission_planner/status', 'GET');
        const el = $('mpStatusText');
        if (!el) return;
        if (res.installed) {
            el.innerHTML = `<span style="color:var(--green)">✅ Instalado</span> — Conecta MP a <strong>UDP (14550)</strong>`;
            $('btnLaunchMP').disabled = false;
        } else {
            el.innerHTML = `<span style="color:var(--amber, #f59e0b)">⚠️ No instalado.</span> Ejecuta <code>scripts/install_mission_planner.sh</code>`;
            $('btnLaunchMP').disabled = true;
        }
    } catch (e) { /* ignore */ }
}

async function launchMissionPlanner() {
    toast('Abriendo Mission Planner...', 'info');
    try {
        const res = await api('/api/mission_planner/launch', 'POST');
        toast(res.message, 'success');
        addLog('Mission Planner lanzado via Wine', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

// ── Step 4: Flight ───────────────────────

function updateTelemetryUI(data, flightState) {
    $('valAlt').innerHTML = `${Math.round(data.relative_alt || 0)}<span class="telemetry-unit">m</span>`;
    $('valSpeed').innerHTML = `${(data.speed || 0).toFixed(1)}<span class="telemetry-unit">m/s</span>`;
    $('valBat').innerHTML = `${data.battery_percent >= 0 ? data.battery_percent : '—'}<span class="telemetry-unit">%</span>`;
    $('valHdg').innerHTML = `${Math.round(data.heading || 0)}<span class="telemetry-unit">°</span>`;
    $('valSat').textContent = data.satellites || 0;
    $('valFix').textContent = data.gps_fix >= 3 ? '3D Fix' : data.gps_fix >= 2 ? '2D' : 'No Fix';
    
    if ($('valWps')) {
        $('valWps').textContent = data.mission_count || 0;
    }

    const badge = $('flightModeBadge');
    const mode = data.flight_mode || 'UNKNOWN';
    badge.textContent = `${mode}${data.armed ? ' ● ARMED' : ''}`;
    badge.className = 'flight-mode-badge';
    if (data.armed) badge.classList.add('armed');
    if (['RTL', 'LAND'].includes(mode)) badge.classList.add('danger');

    const dotGps = $('dotGps');
    if (dotGps) {
        dotGps.className = 'status-dot ' + (data.gps_fix >= 3 ? 'green' : data.gps_fix >= 2 ? 'amber' : 'red');
        const telemGps = $('telemGps');
        if (telemGps) telemGps.textContent = data.gps_fix >= 3 ? `3D Fix (${data.satellites} sat)` : 'Buscando...';
    }
    const dotArm = $('dotArm');
    if (dotArm) {
        dotArm.className = 'status-dot ' + (data.armed ? 'green pulse' : '');
        const telemArm = $('telemArm');
        if (telemArm) telemArm.textContent = data.armed ? 'ARMED' : 'DISARMED';
    }

    const dotGp = $('dotGoproFlight');
    if (dotGp) {
        const isCapturing = data.armed && !isCapturePaused;
        dotGp.className = 'status-dot ' + (isCapturing ? 'green pulse' : (isCapturePaused ? 'amber pulse' : ''));
        const goproStatus = $('goproFlightStatus');
        if (goproStatus) goproStatus.textContent = isCapturing ? 'Capturando' : (isCapturePaused ? 'Pausado' : 'Inactiva');
    }

    if (flightState === 'LANDED' || flightState === 'LANDING') {
        const alert = $('landingAlert');
        if (alert) alert.classList.add('show');
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
            updateTelemetryUI(msg.data, msg.flight_state);
        }
        // Update MAVProxy status from WS
        if (msg.mavproxy) updateMAVProxyUI(msg.mavproxy);
    };
}

// ── Step 5: Download & Results ─────────────────
async function connectGoProBleDownload() {
    const ssid = $('inputManualSsid')?.value.trim();
    const password = $('inputManualPassword')?.value.trim();
    toast('Reconectando GoPro para descarga...', 'info');
    try {
        await api('/api/gopro/connect', 'POST', { mode: 'auto', simulation: isSimulation, ssid, password });
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
        $('syncPanel').style.display = 'block';
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function generateDataset() {
    toast('Generando dataset geoposicionado...', 'info');
    $('btnSync').disabled = true;
    try {
        const res = await api('/api/sync/generate', 'POST');
        toast(`Dataset generado: ${res.entries} entradas`, 'success');
        $('syncPanel').style.display = 'none';
        $('resultsPanel').style.display = 'block';
        $('sumPhotos').textContent = res.entries || 0;
        $('sumMatched').textContent = res.entries || 0;
        $('sumMission').textContent = missionId || '—';
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
        document.querySelector('[data-step="5"]').classList.add('done');
    } catch (e) {
        toast(e.message, 'error');
        $('btnSync').disabled = false;
    }
}

function downloadDatasetCsv() {
    if (missionId) window.open(`/api/dataset/${missionId}`, '_blank');
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
        showGoProConnected('Simulación', 'GP-SIM');
        showTelemConnected('Simulación');
        $('captureActiveRow').style.display = 'flex';
        $('goProCaptureStatus').textContent = '📷 Timelapse simulado';
        goToStep(4);
        toast('Simulación iniciada — observa el vuelo en el mapa', 'success');
        addLog('Simulación completa iniciada', 'success');
    } catch (e) { toast(e.message, 'error'); }
}

// ── Reset ──────────────────────────────────────
async function resetMission() {
    try {
        await api('/api/mission/reset', 'POST');
        if (ws) ws.close();
        ws = null;
        missionId = null;
        isSimulation = false;
        selectedCaptureMode = null;
        isCapturePaused = false;

        $('missionBadge').textContent = 'Sin misión';
        $('simBadge').classList.remove('active');
        $('goProStatusPanel').style.display = 'none';
        $('telemStatusPanel').style.display = 'none';
        $('captureActiveRow').style.display = 'none';
        $('landingAlert').classList.remove('show');
        $('downloadConnectPanel').style.display = 'block';
        $('downloadProgressPanel').style.display = 'none';
        $('syncPanel').style.display = 'none';
        $('resultsPanel').style.display = 'none';
        $('btnFlightPause').style.display = 'none';
        $('btnFlightStop').style.display = 'none';
        if ($('logContainer')) $('logContainer').innerHTML = '';
        document.querySelectorAll('.step').forEach(s => s.classList.remove('done'));
        goToStep(1);
        toast('Misión reiniciada', 'info');
    } catch (e) { toast(e.message, 'error'); }
}

// ── Init ───────────────────────────────────────
updateDateTime();
setInterval(updateDateTime, 1000);
loadPrevMissions();
