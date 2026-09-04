"""
Servidor Web Móvil para Suno AI Downloader
Permite usar la aplicación desde cualquier celular (Android / iOS) conectado a la misma red WiFi.
"""

import os
import sys
import socket
import urllib.parse
from typing import Optional, Dict, Any
import qrcode
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Importar el motor de descarga de suno_downloader sin modificar nada existente
from suno_downloader import SunoScraper, sanitize_filename

# Asegurar UTF-8 en consola de Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = FastAPI(title="Suno AI Mobile Downloader")
scraper = SunoScraper()
DOWNLOADS_DIR = os.path.abspath("downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def get_local_ip() -> str:
    """Detecta la IP local de la computadora en la red Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


class DownloadRequest(BaseModel):
    url: str


class SampleRequest(BaseModel):
    filename: str
    duration_sec: Optional[float] = None
    start_sec: Optional[float] = 0.0
    preset: Optional[str] = None


HTML_MOBILE_UI = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Suno AI Mobile Downloader & Muestras</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #09090b;
            --card-bg: rgba(24, 24, 27, 0.8);
            --card-border: rgba(255, 255, 255, 0.1);
            --primary: #FF0080;
            --primary-gradient: linear-gradient(135deg, #FF0080 0%, #7928CA 100%);
            --accent: #00DFD8;
            --accent-gradient: linear-gradient(135deg, #00DFD8 0%, #0070F3 100%);
            --sample-gradient: linear-gradient(135deg, #7928CA 0%, #4C1D95 100%);
            --text: #f4f4f5;
            --text-dim: #a1a1aa;
            --card-sample: rgba(30, 27, 46, 0.7);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(255, 0, 128, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(121, 40, 202, 0.2) 0%, transparent 40%),
                radial-gradient(circle at 50% 50%, rgba(0, 223, 216, 0.06) 0%, transparent 50%);
            background-attachment: fixed;
            color: var(--text);
            min-height: 100vh;
            padding: 20px 16px 80px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .container {
            width: 100%;
            max-width: 490px;
        }

        header {
            text-align: center;
            margin-bottom: 22px;
            padding-top: 6px;
        }

        .logo-badge {
            display: inline-block;
            background: var(--primary-gradient);
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 10px;
            box-shadow: 0 4px 15px rgba(255, 0, 128, 0.4);
        }

        h1 {
            font-size: 27px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(to right, #FFFFFF, #E4E4E7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .subtitle {
            font-size: 13px;
            color: var(--text-dim);
            margin-top: 4px;
        }

        .card {
            background: var(--card-bg);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border: 1px solid var(--card-border);
            border-radius: 22px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 35px rgba(0, 0, 0, 0.45);
        }

        .input-group {
            position: relative;
            margin-bottom: 14px;
        }

        input[type="text"] {
            width: 100%;
            background: rgba(10, 10, 12, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 14px;
            padding: 15px 46px 15px 16px;
            color: #fff;
            font-family: inherit;
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
        }

        input[type="text"]:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(255, 0, 128, 0.25);
        }

        .paste-btn {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255, 255, 255, 0.12);
            border: none;
            border-radius: 8px;
            padding: 7px 11px;
            color: #fff;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
        }

        .btn-download {
            width: 100%;
            background: var(--primary-gradient);
            border: none;
            border-radius: 14px;
            padding: 16px;
            color: #fff;
            font-family: inherit;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 6px 20px rgba(255, 0, 128, 0.35);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: transform 0.1s, opacity 0.2s;
        }

        .btn-download:active {
            transform: scale(0.98);
        }

        .btn-download:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        /* Result Box */
        .result-box {
            display: none;
            margin-top: 20px;
            animation: fadeIn 0.35s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .song-info {
            display: flex;
            gap: 14px;
            align-items: center;
            margin-bottom: 16px;
        }

        .cover-img {
            width: 74px;
            height: 74px;
            border-radius: 14px;
            object-fit: cover;
            background: #27272a;
            border: 1px solid var(--card-border);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }

        .song-details {
            flex: 1;
            overflow: hidden;
        }

        .song-title {
            font-size: 16px;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #FFFFFF;
        }

        .song-tags {
            font-size: 12px;
            color: var(--primary);
            margin-top: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .song-duration-badge {
            display: inline-block;
            background: rgba(0, 223, 216, 0.15);
            color: var(--accent);
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            margin-top: 4px;
        }

        .audio-player {
            width: 100%;
            margin-bottom: 14px;
            border-radius: 30px;
        }

        .btn-save-phone {
            width: 100%;
            background: #10b981;
            color: #fff;
            text-decoration: none;
            border-radius: 12px;
            padding: 14px;
            font-weight: 700;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.35);
            margin-bottom: 16px;
            transition: transform 0.1s;
        }

        .btn-save-phone:active {
            transform: scale(0.98);
        }

        /* Sample Section (Muestra de Audio) */
        .sample-section {
            background: var(--card-sample);
            border: 1px solid rgba(121, 40, 202, 0.35);
            border-radius: 18px;
            padding: 16px;
            margin-top: 18px;
            box-shadow: 0 6px 24px rgba(121, 40, 202, 0.15);
        }

        .sample-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .sample-title {
            font-size: 14px;
            font-weight: 700;
            color: #E4E4E7;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .sample-tag {
            background: rgba(255, 0, 128, 0.2);
            color: #FF0080;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 8px;
            text-transform: uppercase;
        }

        .sample-desc {
            font-size: 12px;
            color: var(--text-dim);
            margin-bottom: 12px;
            line-height: 1.4;
        }

        .preset-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 6px;
            margin-bottom: 14px;
        }

        .preset-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 10px;
            padding: 9px 4px;
            color: #e4e4e7;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            text-align: center;
            transition: all 0.2s;
        }

        .preset-btn.active {
            background: var(--primary-gradient);
            border-color: var(--primary);
            color: #fff;
            box-shadow: 0 2px 10px rgba(255, 0, 128, 0.35);
        }

        .btn-create-sample {
            width: 100%;
            background: var(--accent-gradient);
            border: none;
            border-radius: 12px;
            padding: 13px;
            color: #000;
            font-family: inherit;
            font-size: 13.5px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            box-shadow: 0 4px 15px rgba(0, 223, 216, 0.3);
            transition: transform 0.1s, opacity 0.2s;
        }

        .btn-create-sample:active {
            transform: scale(0.98);
        }

        .btn-create-sample:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        /* Sample Result Box */
        .sample-result-box {
            display: none;
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px dashed rgba(255, 255, 255, 0.15);
            animation: fadeIn 0.3s ease;
        }

        .btn-save-sample {
            width: 100%;
            background: linear-gradient(135deg, #00DFD8 0%, #10B981 100%);
            color: #000;
            text-decoration: none;
            border-radius: 12px;
            padding: 13px;
            font-weight: 700;
            font-size: 13.5px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            box-shadow: 0 4px 15px rgba(0, 223, 216, 0.35);
            margin-top: 10px;
        }

        .spinner {
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 0.8s linear infinite;
        }

        .spinner-dark {
            border-color: rgba(0,0,0,0.25);
            border-top-color: #000;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .status-badge {
            font-size: 12px;
            text-align: center;
            margin-top: 12px;
            color: var(--accent);
            font-weight: 600;
        }

        /* Recent downloads list */
        .history-title {
            font-size: 14px;
            font-weight: 700;
            margin: 24px 0 10px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .history-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 14px;
            background: rgba(24, 24, 27, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            margin-bottom: 8px;
            gap: 10px;
        }

        .history-item.is-sample {
            border-color: rgba(0, 223, 216, 0.25);
            background: rgba(18, 28, 36, 0.5);
        }

        .history-name {
            font-size: 13px;
            font-weight: 600;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
        }

        .history-badge {
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 6px;
            font-weight: 700;
            background: rgba(0, 223, 216, 0.2);
            color: var(--accent);
            margin-right: 4px;
        }

        .history-btn {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            padding: 6px 12px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-badge">⚡ Suno Downloader HQ</div>
            <h1>Descargar Música y Muestras</h1>
            <p class="subtitle">Descarga canciones completas o extrae muestras (previews) en MP3 320 kbps</p>
        </header>

        <div class="card">
            <div class="input-group">
                <input type="text" id="sunoUrl" placeholder="https://suno.com/song/..." autocomplete="off">
                <button class="paste-btn" onclick="pasteFromClipboard()">Pegar</button>
            </div>

            <button class="btn-download" id="btnDownload" onclick="startDownload()">
                <span>🚀 DESCARGAR CANCIÓN</span>
            </button>

            <div id="statusBadge" class="status-badge" style="display: none;"></div>

            <!-- Result Box -->
            <div class="result-box" id="resultBox">
                <div class="song-info">
                    <img id="resCover" class="cover-img" src="" alt="Cover">
                    <div class="song-details">
                        <div class="song-title" id="resTitle">Título</div>
                        <div class="song-tags" id="resTags">Estilo</div>
                        <div class="song-duration-badge" id="resDuration">⏱️ 0:00</div>
                    </div>
                </div>

                <!-- Full Track Player & Download -->
                <audio id="resAudio" class="audio-player" controls preload="metadata">
                    Tu navegador no soporta el reproductor de audio.
                </audio>

                <a id="resDownloadLink" class="btn-save-phone" href="" download>
                    📥 Guardar Canción Completa
                </a>

                <!-- ✂️ Dedicated Sample Download Section -->
                <div class="sample-section">
                    <div class="sample-header">
                        <div class="sample-title">
                            <span>✂️ Descargar Muestra (Preview)</span>
                        </div>
                        <span class="sample-tag">Clip MP3</span>
                    </div>
                    <p class="sample-desc" id="sampleDescText">
                        Obtén un recorte de la canción para compartir o previsualizar sin descargar la pista entera.
                    </p>

                    <div class="preset-grid">
                        <button class="preset-btn" onclick="selectPreset('30s', this)">⚡ 30s</button>
                        <button class="preset-btn" onclick="selectPreset('60s', this)">⏱️ 1 min</button>
                        <button class="preset-btn" onclick="selectPreset('120s', this)" id="preset2m">⏳ 2 min</button>
                        <button class="preset-btn active" onclick="selectPreset('auto', this)">✨ Auto</button>
                    </div>

                    <button class="btn-create-sample" id="btnCreateSample" onclick="generateSample()">
                        <span>✂️ GENERAR MUESTRA MP3</span>
                    </button>

                    <!-- Sample Result Sub-Box -->
                    <div class="sample-result-box" id="sampleResultBox">
                        <div style="font-size: 12px; color: var(--accent); font-weight: 600; margin-bottom: 8px;" id="sampleResultLabel">
                            🎧 Muestra generada:
                        </div>
                        <audio id="sampleAudioPlayer" class="audio-player" controls preload="metadata">
                            Tu navegador no soporta el reproductor de audio.
                        </audio>
                        <a id="sampleDownloadLink" class="btn-save-sample" href="" download>
                            📥 Guardar Muestra en mi Celular
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <div class="history-title">📂 Archivos en tu Servidor</div>
        <div id="historyList"></div>
    </div>

    <script>
        let currentFilename = "";
        let currentTotalDuration = 0;
        let selectedPreset = "auto";

        async function pasteFromClipboard() {
            try {
                const text = await navigator.clipboard.readText();
                if (text) {
                    document.getElementById('sunoUrl').value = text.trim();
                }
            } catch (err) {
                alert('Toca la caja de texto y mantén presionado para pegar.');
            }
        }

        function selectPreset(preset, btnElement) {
            selectedPreset = preset;
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            if (btnElement) {
                btnElement.classList.add('active');
            }
        }

        async function startDownload() {
            const urlInput = document.getElementById('sunoUrl');
            const url = urlInput.value.trim();
            if (!url) {
                alert('Por favor pega un enlace de Suno.');
                return;
            }

            const btn = document.getElementById('btnDownload');
            const statusBadge = document.getElementById('statusBadge');
            const resultBox = document.getElementById('resultBox');
            const sampleResultBox = document.getElementById('sampleResultBox');

            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> Descifrando y procesando...';
            statusBadge.style.display = 'block';
            statusBadge.innerText = 'Conectando con Suno y descifrando audio...';
            resultBox.style.display = 'none';
            sampleResultBox.style.display = 'none';

            try {
                const response = await fetch('/api/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });

                const data = await response.json();

                if (!response.ok || data.error) {
                    throw new Error(data.error || 'Error al procesar la canción.');
                }

                currentFilename = data.filename;
                currentTotalDuration = data.duration_seconds || 0;

                // Show results
                document.getElementById('resTitle').innerText = data.title;
                document.getElementById('resTags').innerText = data.tags || 'Suno AI Track';
                document.getElementById('resCover').src = data.cover_url || '';
                document.getElementById('resDuration').innerText = `⏱️ Duración: ${data.duration_formatted || 'Desconocida'}`;

                const audioPlayer = document.getElementById('resAudio');
                audioPlayer.src = data.download_url;
                
                const dlLink = document.getElementById('resDownloadLink');
                dlLink.href = data.download_url;
                dlLink.setAttribute('download', data.filename);

                // Update sample description with suggested duration
                const suggestedDur = data.suggested_sample_formatted || '1-2 minutos';
                document.getElementById('sampleDescText').innerText = 
                    `Canción de ${data.duration_formatted || 'duración estándar'}. Duración de muestra sugerida: ${suggestedDur}.`;

                statusBadge.innerText = '✅ ¡Canción descifrada con éxito!';
                resultBox.style.display = 'block';
                loadHistory();

            } catch (err) {
                alert('Error: ' + err.message);
                statusBadge.innerText = '❌ ' + err.message;
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🚀 DESCARGAR CANCIÓN';
            }
        }

        async function generateSample() {
            if (!currentFilename) {
                alert('Primero descarga una canción.');
                return;
            }

            const btn = document.getElementById('btnCreateSample');
            const sampleResultBox = document.getElementById('sampleResultBox');
            const sampleAudio = document.getElementById('sampleAudioPlayer');
            const sampleDlLink = document.getElementById('sampleDownloadLink');
            const sampleLabel = document.getElementById('sampleResultLabel');

            btn.disabled = true;
            btn.innerHTML = '<div class="spinner spinner-dark"></div> Recortando muestra con FFmpeg...';

            try {
                const response = await fetch('/api/sample', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: currentFilename,
                        preset: selectedPreset
                    })
                });

                const data = await response.json();

                if (!response.ok || data.error) {
                    throw new Error(data.error || 'Error al generar la muestra.');
                }

                sampleAudio.src = data.sample_url;
                sampleDlLink.href = data.sample_url;
                sampleDlLink.setAttribute('download', data.filename);
                sampleLabel.innerText = `🎧 Muestra lista (${Math.round(data.sample_duration)}s con suavizado):`;

                sampleResultBox.style.display = 'block';
                loadHistory();

            } catch (err) {
                alert('Error al generar muestra: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span>✂️ GENERAR MUESTRA MP3</span>';
            }
        }

        async function loadHistory() {
            try {
                const res = await fetch('/api/files');
                const files = await res.json();
                const list = document.getElementById('historyList');
                list.innerHTML = '';
                
                if (files.length === 0) {
                    list.innerHTML = '<div style="color:#71717a; font-size:12px; text-align:center;">No hay descargas recientes aún.</div>';
                    return;
                }

                files.forEach(f => {
                    const item = document.createElement('div');
                    const isSample = f.name.includes('_muestra_') || f.name.includes('[Muestra');
                    item.className = 'history-item' + (isSample ? ' is-sample' : '');
                    
                    const badge = isSample ? '<span class="history-badge">✂️ Muestra</span>' : '';
                    item.innerHTML = `
                        <span class="history-name">${badge}🎵 ${f.name}</span>
                        <a class="history-btn" href="/downloads/${encodeURIComponent(f.filename)}" download>Descargar</a>
                    `;
                    list.appendChild(item);
                });
            } catch (e) {
                console.error(e);
            }
        }

        // Cargar historial al iniciar
        loadHistory();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_MOBILE_UI


@app.post("/api/download")
async def api_download(req: DownloadRequest):
    try:
        url = req.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL requerida")

        res = scraper.download_song(url, output_dir=DOWNLOADS_DIR)
        info = res["info"]
        mp3_file = os.path.basename(res["mp3_path"])
        duration = res.get("duration", 0.0)
        dur_m = int(duration // 60)
        dur_s = int(duration % 60)
        duration_formatted = f"{dur_m}:{dur_s:02d}"

        # Cálculo sugerido para la muestra
        suggested_sec = 60
        if duration <= 60:
            suggested_sec = 30
        elif duration > 180:
            suggested_sec = 120  # e.g. 2 min para canciones largas
        suggested_formatted = f"{int(suggested_sec // 60)} min" if suggested_sec >= 60 else f"{int(suggested_sec)} seg"

        cover_url = ""
        if res.get("cover_path") and os.path.exists(res["cover_path"]):
            cover_file = os.path.basename(res["cover_path"])
            cover_url = f"/downloads/{urllib.parse.quote(cover_file)}"
        elif info.get("image_url"):
            cover_url = info["image_url"]

        return {
            "success": True,
            "title": info["title"],
            "tags": info.get("tags", ""),
            "filename": mp3_file,
            "download_url": f"/downloads/{urllib.parse.quote(mp3_file)}",
            "cover_url": cover_url,
            "duration_seconds": duration,
            "duration_formatted": duration_formatted,
            "suggested_sample_seconds": suggested_sec,
            "suggested_sample_formatted": suggested_formatted
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/sample")
async def api_generate_sample(req: SampleRequest):
    """Genera una muestra/preview en MP3 de una canción existente."""
    try:
        filename = req.filename.strip()
        if not filename:
            raise HTTPException(status_code=400, detail="Nombre de archivo requerido")

        input_path = os.path.join(DOWNLOADS_DIR, filename)
        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="El archivo base no existe en descargas")

        total_dur = scraper.get_audio_duration(input_path)
        duration_sec = req.duration_sec
        preset = (req.preset or "").lower()

        if preset == "30s":
            duration_sec = 30.0
        elif preset in ("60s", "1m"):
            duration_sec = 60.0
        elif preset in ("120s", "2m"):
            duration_sec = 120.0
        elif preset in ("half", "50%"):
            duration_sec = max(15.0, total_dur * 0.5) if total_dur > 0 else 60.0
        elif preset == "auto":
            duration_sec = None  # SunoScraper calculará automáticamente (ej. 2 min si > 3m)

        sample_res = scraper.create_audio_sample(
            input_mp3=input_path,
            duration_sec=duration_sec,
            start_sec=req.start_sec or 0.0,
            apply_fade=True
        )

        sample_filename = sample_res["filename"]
        return {
            "success": True,
            "filename": sample_filename,
            "sample_url": f"/downloads/{urllib.parse.quote(sample_filename)}",
            "sample_duration": sample_res["actual_sample_duration"],
            "total_duration": sample_res["total_duration"]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/downloads/{filename}")
async def download_file_endpoint(filename: str):
    file_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(
        file_path,
        media_type="audio/mpeg" if filename.endswith(".mp3") else "image/jpeg",
        filename=filename
    )


@app.get("/api/files")
async def list_downloaded_files():
    files = []
    if os.path.exists(DOWNLOADS_DIR):
        for f in os.listdir(DOWNLOADS_DIR):
            if f.endswith(".mp3"):
                clean_name = f.replace(".mp3", "")
                files.append({
                    "filename": f,
                    "name": clean_name
                })
    files.reverse()
    return files[:20]


def run_server():
    local_ip = get_local_ip()
    port = 8000
    mobile_url = f"http://{local_ip}:{port}"

    print("\n" + "="*58)
    print(" 🚀 SERVIDOR MÓVIL DE SUNO AI ACTIVADO")
    print("="*58)
    print(f"\n📲 ABRE ESTE ENLACE EN EL NAVEGADOR DE TU CELULAR:\n")
    print(f"👉 \033[92m{mobile_url}\033[0m\n")
    print("="*58)
    print("📷 O ESCANEA ESTE CÓDIGO QR CON LA CÁMARA DE TU CELULAR:")
    print("="*58 + "\n")

    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(mobile_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass

    print("\n" + "-"*58)
    print("💡 Asegúrate de que tu celular esté conectado al mismo Wi-Fi.")
    print("Presiona Ctrl + C en esta ventana para detener el servidor.")
    print("-"*58 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    run_server()

