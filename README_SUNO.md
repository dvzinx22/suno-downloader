# 🎵 Suno AI Downloader & Sample Extractor HQ

Herramienta para descargar y descifrar canciones compartidas de **Suno.com** en MP3 estándar a 320 kbps de alta fidelidad, con portada, letras y **generador/descargador de muestras de audio (previews/clips)**.

---

## 🚀 Formas de Uso

### 1. Desde tu Celular / Navegador Web (Recomendado para Móviles)
Haz doble clic en:
👉 `iniciar_para_celular.bat`

- Abre la dirección IP mostrada o escanea el código QR con tu celular.
- Descarga la canción completa directamente a tu teléfono.
- **✂️ Apartado de Muestras (Previews)**: Extrae un clip de 30s, 1 min, 2 min o proporcional a la duración total con suavizado automático (fade-in / fade-out) y escúchalo o descárgalo en tu celular.

---

### 2. Con la Interfaz de Escritorio (GUI)
Haz doble clic en:
👉 `iniciar_suno_downloader.bat`

- Pega el enlace de Suno con el botón **📋 Pegar Enlace**.
- Visualiza la carátula, título, tags de estilo, letra/prompt y duración exacta.
- Descarga la canción completa en MP3 320 kbps.
- **✂️ Sección de Muestras**: Selecciona la duración deseada (30s, 1m, 2m, mitad o automática) y pulsa **✂️ Guardar Muestra MP3** para crear el clip al instante y reproducirlo.

---

### 3. Desde la Terminal / Consola

#### Abrir la interfaz gráfica:
```bash
python suno_downloader.py --gui
```

#### Descarga directa por comando:
```bash
python suno_downloader.py https://suno.com/song/c7e0c4ce-4d51-4d3b-9e47-e170c0c7a10a
```

#### Descargar canción y generar muestra automáticamente (ej. 2 minutos o auto):
```bash
python suno_downloader.py https://suno.com/song/c7e0c4ce-4d51-4d3b-9e47-e170c0c7a10a --sample 120
```

---

## 🔗 Formatos de Enlace Compatibles

- `https://suno.com/song/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- `https://suno.com/s/xxxxxx` (enlaces acortados)
- `https://app.suno.ai/song/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- O directamente el UUID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

---

## ⚙️ ¿Cómo Funciona el Generador de Muestras?

1. **Detección de Duración**: Analiza los segundos exactos de la pista MP3 mediante FFmpeg.
2. **Cálculo Proporcional**: Si la canción dura ~5 minutos, genera una muestra sugerida de 2 minutos (o la duración que elijas).
3. **Corte y Suavizado HQ**: Aplica filtros de Fade-In y Fade-Out para evitar cortes abruptos y exporta un archivo MP3 independiente a 320 kbps listo para reproducir y compartir.

