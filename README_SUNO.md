# 🎵 Suno AI Downloader & Scraper

Herramienta para descargar canciones compartidas de **Suno.com** mediante inspección de metadatos, scraping y extracción directa desde la CDN.

---

## 🚀 Formas de Uso

### 1. Con Doble Clic (Recomendado)
Haz doble clic en el archivo:
👉 `iniciar_suno_downloader.bat`

Se abrirá la **Interfaz Gráfica (GUI)** donde podrás:
- Pegar el enlace compartido con el botón **📋 Pegar Enlace**.
- Ver la miniatura de la portada, el título, etiquetas de estilo y la letra/prompt.
- Elegir si quieres guardar la portada `.png`, el video `.mp4` y la letra `.txt`.
- Cambiar la carpeta de descarga o abrirla directamente con **📂 Abrir Carpeta**.

---

### 2. Desde la Terminal / Consola

#### Abrir la interfaz gráfica:
```bash
python suno_downloader.py --gui
```

#### Descarga directa por comando:
```bash
python suno_downloader.py https://suno.com/song/c7e0c4ce-4d51-4d3b-9e47-e170c0c7a10a
```

#### Descargar también video MP4 y guardar en otra carpeta:
```bash
python suno_downloader.py https://suno.com/song/c7e0c4ce-4d51-4d3b-9e47-e170c0c7a10a --video -o "mis_canciones"
```

---

## 🔗 Formatos de Enlace Compatibles

- `https://suno.com/song/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- `https://suno.com/s/xxxxxx` (enlaces acortados)
- `https://app.suno.ai/song/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- O directamente el UUID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

---

## ⚙️ ¿Cómo Funciona?

1. **Resolución y Redirecciones**: Detecta el UUID del clip musical siguiendo redirecciones HTTP con headers reales de navegador.
2. **Inspección de Metadatos**: Extrae título, etiquetas de estilo, letra del prompt y portada desde las etiquetas OpenGraph y el estado de Next.js (`__NEXT_DATA__`).
3. **Extracción Directa de Audio**: Localiza la URL de transmisión directa en la CDN de Suno (`cdn1.suno.ai` / `cdn2.suno.ai` / `audiopipe`) y descarga el MP3 en alta calidad.
