# 🎵 Suno AI Downloader, WAV & Separador de Pistas HQ

Herramienta completa para descargar, descifrar canciones compartidas de **Suno.com** en **MP3 320 kbps** o **WAV Lossless (Audio sin compresión)**, extraer **muestras de audio (clips)** y **separar la pista instrumental y la voz (acapella)** con procesamiento DSP estéreo de alta fidelidad.

---

## ✨ Nuevas Características

- 💿 **Descarga en WAV Lossless (PCM 16-bit)**: Máxima fidelidad de audio para edición, producción y mezcla.
- 🎵 **Descarga en MP3 estándar (320 kbps HQ)**: Compatibilidad total con reproductores y dispositivos móviles.
- 🎤 **Separador de Pista y Voz (Stems)**:
  - 🎹 **Pista Instrumental**: Aísla la música/karaoke preservando bombos, bajos y frecuencias rítmicas.
  - 🎙️ **Solo Voz (Acapella)**: Aísla la voz limpia y formantes vocales para remixes o estudio.
- ✂️ **Extractor de Muestras (Previews)**: Genera clips automáticos (30s, 1m, 2m) con desvanecimiento de entrada y salida (fade-in / fade-out).

---

## 🚀 Formas de Uso

### 1. Desde tu Celular / Navegador Web (Recomendado para Móviles)
Haz doble clic en:
👉 `iniciar_para_celular.bat`

- Abre la dirección IP mostrada o escanea el código QR con tu celular.
- Elige el formato deseado: **MP3 (320 kbps)** o **WAV (Lossless)**.
- **🎤 Separador de Pista y Voz**: Presiona *✨ SEPARAR EN PISTA Y VOZ* para generar y escuchar individualmente la pista instrumental y la voz, con botones de descarga directa a tu celular.
- **✂️ Muestras**: Extrae clips de 30s, 1 min, 2 min o Auto.

---

### 2. Con la Interfaz de Escritorio (GUI)
Haz doble clic en:
👉 `iniciar_suno_downloader.bat`

- Selecciona el formato **MP3** o **WAV**.
- Pega el enlace de Suno con el botón **📋 Pegar**.
- Descarga la canción completa con su carátula y letras.
- Usa el apartado **🎤 SEPARADOR DE PISTA Y VOZ** para generar y reproducir la Pista Instrumental y la Voz por separado.
- Usa la sección **✂️ DESCARGAR MUESTRA** para guardar clips cortos.

---

### 3. Desde la Terminal / Consola

#### Abrir la interfaz gráfica:
```bash
python suno_downloader.py --gui
```

#### Descargar en WAV sin compresión:
```bash
python suno_downloader.py https://suno.com/song/ID_DE_LA_CANCION -f wav
```

#### Descargar y separar inmediatamente en Pista Instrumental y Voz:
```bash
python suno_downloader.py https://suno.com/song/ID_DE_LA_CANCION --separate
```

#### Descargar en WAV, separar pista/voz y generar muestra:
```bash
python suno_downloader.py https://suno.com/song/ID_DE_LA_CANCION -f wav --separate --sample 60
```

---

## 🔗 Formatos de Enlace Compatibles

- `https://suno.com/song/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- `https://suno.com/s/xxxxxx` (enlaces acortados)
- `https://app.suno.ai/song/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- O directamente el UUID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`


