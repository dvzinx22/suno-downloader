"""
Servidor Web Móvil para Suno AI Downloader
Permite usar la aplicación desde cualquier celular (Android / iOS) conectado a la misma red WiFi.
"""

import os
import sys
import socket
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


HTML_MOBILE_UI = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Suno AI Mobile Downloader</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #09090b;
            --card-bg: rgba(24, 24, 27, 0.75);
            --border: rgba(255, 255, 255, 0.1);
            --primary: #FF0080;
            --primary-gradient: linear-gradient(135deg, #FF0080 0%, #7928CA 100%);
            --accent: #00DFD8;
            --text: #f4f4f5;
            --text-dim: #a1a1aa;
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
                radial-gradient(circle at 90% 80%, rgba(121, 40, 202, 0.18) 0%, transparent 40%);
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
            max-width: 480px;
        }

        header {
            text-align: center;
            margin-bottom: 24px;
            padding-top: 10px;
        }

        .logo-badge {
            display: inline-block;
            background: var(--primary-gradient);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 8px;
            box-shadow: 0 4px 15px rgba(255, 0, 128, 0.4);
        }

        h1 {
            font-size: 26px;
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
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }

        .input-group {
            position: relative;
            margin-bottom: 14px;
        }

        input[type="text"] {
            width: 100%;
            background: rgba(10, 10, 12, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 14px;
            padding: 15px 44px 15px 16px;
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
            background: rgba(255, 255, 255, 0.1);
            border: none;
            border-radius: 8px;
            padding: 6px 10px;
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

        /* Result Preview Box */
        .result-box {
            display: none;
            margin-top: 20px;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .song-info {
            display: flex;
            gap: 14px;
            align-items: center;
            margin-bottom: 16px;
        }

        .cover-img {
            width: 72px;
            height: 72px;
            border-radius: 12px;
            object-fit: cover;
            background: #27272a;
            border: 1px solid var(--border);
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
        }

        .song-tags {
            font-size: 12px;
            color: var(--primary);
            margin-top: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .audio-player {
            width: 100%;
            margin-bottom: 16px;
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
            margin: 20px 0 10px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .history-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 14px;
            background: rgba(24, 24, 27, 0.5);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 8px;
            gap: 10px;
        }

        .history-name {
            font-size: 13px;
            font-weight: 600;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
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
            <h1>Descargar en el Móvil</h1>
            <p class="subtitle">Pega el link de Suno y descárgalo como MP3 (320 kbps)</p>
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
                    </div>
                </div>

                <audio id="resAudio" class="audio-player" controls preload="metadata">
                    Tu navegador no soporta el reproductor de audio.
                </audio>

                <a id="resDownloadLink" class="btn-save-phone" href="" download>
                    📥 Guardar MP3 en mi Celular
                </a>
            </div>
        </div>

        <div class="history-title">📂 Canciones en tu Servidor</div>
        <div id="historyList"></div>
    </div>

    <script>
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

            btn.disabled = true;
            btn.innerHTML = '<div class="spinner"></div> Descifrando y procesando...';
            statusBadge.style.display = 'block';
            statusBadge.innerText = 'Conectando con Suno y descifrando audio...';
            resultBox.style.display = 'none';

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

                // Show results
                document.getElementById('resTitle').innerText = data.title;
                document.getElementById('resTags').innerText = data.tags || 'Suno Music';
                document.getElementById('resCover').src = data.cover_url || '';
                
                const audioPlayer = document.getElementById('resAudio');
                audioPlayer.src = data.download_url;
                
                const dlLink = document.getElementById('resDownloadLink');
                dlLink.href = data.download_url;
                dlLink.setAttribute('download', data.filename);

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
                    item.className = 'history-item';
                    item.innerHTML = `
                        <span class="history-name">🎵 ${f.name}</span>
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
            "cover_url": cover_url
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
    return files[:15]


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
