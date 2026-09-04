"""
Suno AI Music Downloader & Decryptor
Descarga y descifra canciones de Suno AI (Sistema Mango DRM / AES-128-CTR)
Generando archivos MP3 estándar a 320 kbps de alta fidelidad, con portada y letra.
"""

import os
import re
import sys
import json
import base64
import hashlib
import subprocess
import urllib.parse
from typing import Optional, Dict, Any, Callable
import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import imageio_ffmpeg

# Configurar codificación segura para consola en Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://suno.com/",
    "Origin": "https://suno.com"
}

UUID_REGEX = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.IGNORECASE)


def sanitize_filename(name: str) -> str:
    """Limpia caracteres no permitidos en nombres de archivo."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.strip().replace("\n", " ").replace("\r", "")
    return clean[:90] if clean else "suno_song"


class SunoScraper:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def extract_song_id(self, url_or_id: str) -> Optional[str]:
        """Extrae el UUID de la canción de Suno."""
        match = UUID_REGEX.search(url_or_id)
        if match:
            return match.group(1)
        return None

    def scrape_song_info(self, url: str) -> Dict[str, Any]:
        """Extrae metadatos, imagen y URLs desde la página de Suno."""
        url = url.strip()
        if not url.startswith("http"):
            song_id = self.extract_song_id(url)
            if song_id:
                url = f"https://suno.com/song/{song_id}"
            else:
                raise ValueError(f"URL o ID no válido: {url}")

        song_id = self.extract_song_id(url)

        # Realizar petición HTTP siguiendo redirecciones
        response = self.session.get(url, timeout=15, allow_redirects=True)
        final_url = response.url
        if not song_id:
            song_id = self.extract_song_id(final_url)

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        info: Dict[str, Any] = {
            "id": song_id,
            "title": "Suno AI Song",
            "audio_url": None,
            "image_url": None,
            "prompt": "",
            "tags": "",
            "source_url": final_url,
        }

        # Extraer Título
        og_title = soup.find("meta", property="og:title") or soup.find("meta", {"name": "twitter:title"})
        if og_title and og_title.get("content"):
            title_clean = og_title["content"].replace(" | Suno", "").replace(" on Suno", "").strip()
            if title_clean:
                info["title"] = title_clean

        # Extraer Portada
        og_image = soup.find("meta", property="og:image") or soup.find("meta", {"name": "twitter:image"})
        if og_image and og_image.get("content"):
            info["image_url"] = og_image["content"]

        # Extraer Descripción / Prompt
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", {"name": "description"})
        if og_desc and og_desc.get("content"):
            info["prompt"] = og_desc["content"]

        # Extraer Tags de estilo
        tags_match = re.search(r'\"tags\"\s*:\s*\"([^\"]+)\"', html)
        if tags_match:
            info["tags"] = tags_match.group(1)

        # Buscar URL de audio de CloudFront en el HTML
        cf_matches = re.findall(r'https?://[^\s"\'<>\\]+\.cloudfront\.net/[^\s"\'<>\\]+\.(?:m4a|mp3|wav)', html)
        if cf_matches:
            info["audio_url"] = cf_matches[0]
        elif song_id:
            info["audio_url"] = f"https://d2lwuy8qc234o3.cloudfront.net/1/clip/{song_id}.m4a"

        if not info["image_url"] and song_id:
            info["image_url"] = f"https://cdn2.suno.ai/image_large_{song_id}.jpeg"

        return info

    def decrypt_and_download(
        self,
        song_id: str,
        stream_url: str,
        output_mp3_path: str,
        progress_callback: Optional[Callable[[str, int, int, float], None]] = None
    ) -> str:
        """
        Descifra el audio de Suno usando el sistema Mango (AES-GCM unwrapping + AES-128-CTR stream decryption)
        y lo convierte a MP3 estándar compatible con todos los reproductores.
        """
        if progress_callback:
            progress_callback("licencia", 0, 0, 10.0)

        # 1. Obtener claves de licencia Mango
        rights_url = "https://studio-api.prod.suno.com/api/mango/rights"
        payload = {
            "content_params": {
                "content_id": song_id,
                "content_type": "clip"
            }
        }
        rights_res = self.session.post(rights_url, json=payload, timeout=15)
        if rights_res.status_code != 200:
            raise Exception(f"No se pudo obtener la licencia de audio de Suno (HTTP {rights_res.status_code})")

        rights_data = rights_res.json()
        glt = rights_data["glt"]
        wrapped_key_b64 = rights_data["key"]
        wrapped_iv_b64 = rights_data["iv"]

        # 2. Desempaquetar clave y vector de inicialización (AES-GCM con SHA256 de GLT)
        user_key = hashlib.sha256(glt.encode("utf-8")).digest()
        aes_gcm = AESGCM(user_key)
        aad = song_id.encode("utf-8")

        wrapped_key = base64.b64decode(wrapped_key_b64)
        content_key = aes_gcm.decrypt(wrapped_key[:12], wrapped_key[12:], aad)

        wrapped_iv = base64.b64decode(wrapped_iv_b64)
        content_iv = aes_gcm.decrypt(wrapped_iv[:12], wrapped_iv[12:], aad)

        # 3. Descargar el flujo cifrado con progreso
        if progress_callback:
            progress_callback("descargando", 0, 0, 25.0)

        res = self.session.get(stream_url, stream=True, timeout=30)
        if res.status_code != 200:
            raise Exception(f"Error al descargar stream de audio (HTTP {res.status_code})")

        total_size = int(res.headers.get("content-length", 0))
        encrypted_chunks = []
        downloaded = 0

        for chunk in res.iter_content(chunk_size=64 * 1024):
            if chunk:
                encrypted_chunks.append(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size > 0:
                    pct = 25.0 + ((downloaded / total_size) * 50.0)
                    progress_callback("descargando", downloaded, total_size, pct)

        encrypted_data = b"".join(encrypted_chunks)
        if len(encrypted_data) < 50000:
            raise Exception("El archivo descargado está incompleto o vacío.")

        # 4. Descifrar con AES-128-CTR
        if progress_callback:
            progress_callback("descifrando", downloaded, total_size, 80.0)

        cipher = Cipher(algorithms.AES(content_key), modes.CTR(content_iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_audio = decryptor.update(encrypted_data) + decryptor.finalize()

        # Guardar archivo temporal descifrado
        temp_decrypted = output_mp3_path + ".tmp.m4a"
        with open(temp_decrypted, "wb") as f:
            f.write(decrypted_audio)

        # 5. Convertir a MP3 estándar con FFmpeg (320 kbps)
        if progress_callback:
            progress_callback("convirtiendo", downloaded, total_size, 90.0)

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-i", temp_decrypted,
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            output_mp3_path
        ]
        conv_res = subprocess.run(cmd, capture_output=True, text=True)

        # Limpiar archivo temporal
        if os.path.exists(temp_decrypted):
            try:
                os.remove(temp_decrypted)
            except Exception:
                pass

        if conv_res.returncode != 0:
            # Fallback: renombrar el m4a descifrado si falla ffmpeg
            fallback_m4a = output_mp3_path.replace(".mp3", ".m4a")
            with open(fallback_m4a, "wb") as f:
                f.write(decrypted_audio)
            return fallback_m4a

        if progress_callback:
            progress_callback("completado", downloaded, total_size, 100.0)

        return output_mp3_path

    def get_audio_duration(self, file_path: str) -> float:
        """Obtiene la duración del archivo de audio en segundos mediante FFmpeg."""
        if not os.path.exists(file_path):
            return 0.0
        try:
            cmd = [self.ffmpeg_exe, "-i", file_path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
            if match:
                h, m, s = match.groups()
                return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            pass
        return 0.0

    def create_audio_sample(
        self,
        input_mp3: str,
        output_sample_mp3: Optional[str] = None,
        start_sec: float = 0.0,
        duration_sec: Optional[float] = None,
        apply_fade: bool = True
    ) -> Dict[str, Any]:
        """
        Genera una muestra/preview en MP3 de una parte de la canción.
        Si no se especifica duration_sec, se calcula automáticamente según la duración total:
          - Si dura <= 60s: muestra de 30s.
          - Si dura <= 180s (3m): muestra de 60s (1m).
          - Si dura > 180s (ej. 4-5m): muestra de 120s (2m) o 45% del total.
        """
        if not os.path.exists(input_mp3):
            raise FileNotFoundError(f"El archivo de audio no existe: {input_mp3}")

        total_duration = self.get_audio_duration(input_mp3)

        # Cálculo inteligente de duración de muestra
        if duration_sec is None or duration_sec <= 0:
            if total_duration <= 0:
                duration_sec = 60.0
            elif total_duration <= 60:
                duration_sec = min(30.0, total_duration)
            elif total_duration <= 180:
                duration_sec = 60.0
            else:
                # Ejemplo: canciones de 4-5 minutos -> muestra de 2 minutos (120s)
                duration_sec = min(120.0, total_duration * 0.45)

        # Asegurar límites válidos
        if total_duration > 0:
            start_sec = max(0.0, min(start_sec, max(0.0, total_duration - 5.0)))
            duration_sec = min(duration_sec, total_duration - start_sec)
        else:
            start_sec = max(0.0, start_sec)
            duration_sec = max(5.0, duration_sec)

        if not output_sample_mp3:
            base, ext = os.path.splitext(input_mp3)
            dur_label = f"{int(duration_sec)}s" if duration_sec < 60 else f"{int(duration_sec // 60)}m{int(duration_sec % 60):02d}s" if duration_sec % 60 else f"{int(duration_sec // 60)}m"
            output_sample_mp3 = f"{base}_muestra_{dur_label}{ext}"

        # Aplicar suavizado (fade-in y fade-out)
        filters = []
        if apply_fade and duration_sec >= 4.0:
            fade_in_len = min(1.5, duration_sec * 0.08)
            fade_out_len = min(2.5, duration_sec * 0.12)
            fade_out_start = max(0.1, duration_sec - fade_out_len)
            filters.append(f"afade=t=in:ss=0:d={fade_in_len:.2f}")
            filters.append(f"afade=t=out:st={fade_out_start:.2f}:d={fade_out_len:.2f}")

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-ss", str(round(start_sec, 2)),
            "-t", str(round(duration_sec, 2)),
            "-i", input_mp3
        ]

        if filters:
            cmd.extend(["-af", ",".join(filters)])

        cmd.extend([
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            output_sample_mp3
        ])

        conv_res = subprocess.run(cmd, capture_output=True, text=True)
        if conv_res.returncode != 0:
            raise Exception(f"Error al generar la muestra con FFmpeg: {conv_res.stderr}")

        sample_duration = self.get_audio_duration(output_sample_mp3)

        return {
            "sample_path": output_sample_mp3,
            "filename": os.path.basename(output_sample_mp3),
            "total_duration": total_duration,
            "start_sec": start_sec,
            "duration_sec": duration_sec,
            "actual_sample_duration": sample_duration
        }

    def download_cover(self, url: str, destination_path: str):
        """Descarga la portada."""
        try:
            res = self.session.get(url, timeout=15)
            if res.status_code == 200:
                with open(destination_path, "wb") as f:
                    f.write(res.content)
                return True
        except Exception:
            pass
        return False

    def download_song(
        self,
        url: str,
        output_dir: str = "downloads",
        save_cover: bool = True,
        save_metadata: bool = True,
        progress_callback: Optional[Callable[[str, int, int, float], None]] = None
    ) -> Dict[str, Any]:
        """Descarga, descifra y procesa la canción completa."""
        info = self.scrape_song_info(url)
        os.makedirs(output_dir, exist_ok=True)

        clean_title = sanitize_filename(info["title"])
        song_id = info["id"] or "track"
        base_name = f"{clean_title} ({song_id[:8]})"

        result = {
            "info": info,
            "mp3_path": None,
            "cover_path": None,
            "metadata_path": None,
            "duration": 0.0
        }

        # Descifrar y Guardar MP3
        mp3_out = os.path.join(output_dir, f"{base_name}.mp3")
        stream_url = info.get("audio_url") or f"https://d2lwuy8qc234o3.cloudfront.net/1/clip/{song_id}.m4a"

        final_audio_path = self.decrypt_and_download(
            song_id,
            stream_url,
            mp3_out,
            progress_callback
        )
        result["mp3_path"] = final_audio_path
        result["duration"] = self.get_audio_duration(final_audio_path)

        # Guardar Portada
        if save_cover and info.get("image_url"):
            cover_ext = ".jpeg" if ".jpeg" in info["image_url"] else ".png"
            cover_path = os.path.join(output_dir, f"{base_name}{cover_ext}")
            if self.download_cover(info["image_url"], cover_path):
                result["cover_path"] = cover_path

        # Guardar Letra y Metadatos
        if save_metadata:
            meta_path = os.path.join(output_dir, f"{base_name}_info.txt")
            with open(meta_path, "w", encoding="utf-8") as f:
                f.write(f"Título: {info['title']}\n")
                f.write(f"ID Suno: {info['id']}\n")
                f.write(f"Enlace Original: {info['source_url']}\n")
                f.write(f"Tags / Estilo: {info['tags']}\n")
                dur_m = int(result["duration"] // 60)
                dur_s = int(result["duration"] % 60)
                f.write(f"Duración: {dur_m}:{dur_s:02d} ({result['duration']:.1f}s)\n")
                f.write("-" * 50 + "\n")
                f.write("LETRA / PROMPT:\n")
                f.write(f"{info['prompt'] or 'No disponible'}\n")
            result["metadata_path"] = meta_path

        return result


def launch_cli():
    import argparse
    parser = argparse.ArgumentParser(description="Descargador y Descifrador de canciones de Suno AI")
    parser.add_argument("url", nargs="?", help="URL o ID de la canción de Suno")
    parser.add_argument("-o", "--output", default="downloads", help="Carpeta de destino")
    parser.add_argument("--no-cover", action="store_true", help="No descargar portada")
    parser.add_argument("--sample", nargs="?", const="auto", default=None, help="Generar muestra de audio (ej: 30, 60, 120 o auto)")
    parser.add_argument("--gui", action="store_true", help="Abrir interfaz gráfica")

    args = parser.parse_args()

    if args.gui or len(sys.argv) == 1:
        launch_gui()
        return

    if not args.url:
        print("Uso: python suno_downloader.py https://suno.com/song/ID_DE_LA_CANCION [--sample 120]")
        return

    print(f"\n🎵 Conectando y descifrando canción de Suno: {args.url}")
    scraper = SunoScraper()

    try:
        def progress_cb(stage, downloaded, total, percent):
            if total > 0:
                mb_d = downloaded / (1024 * 1024)
                mb_t = total / (1024 * 1024)
                print(f"\r[{stage.upper()}] [{percent:.1f}%] {mb_d:.2f}MB / {mb_t:.2f}MB", end="")
            else:
                print(f"\r[{stage.upper()}] Procesando...", end="")

        res = scraper.download_song(
            args.url,
            output_dir=args.output,
            save_cover=not args.no_cover,
            progress_callback=progress_cb
        )
        print("\n\n✅ ¡Descarga y descifrado completados con éxito!")
        print(f"🎵 Título: {res['info']['title']}")
        dur_m = int(res['duration'] // 60)
        dur_s = int(res['duration'] % 60)
        print(f"⏱️ Duración total: {dur_m}:{dur_s:02d} ({res['duration']:.1f}s)")
        print(f"🎧 Archivo MP3 (320 kbps): {res['mp3_path']}")
        if res.get('cover_path'):
            print(f"🖼️ Portada: {res['cover_path']}")
        if res.get('metadata_path'):
            print(f"📄 Letra y Metadatos: {res['metadata_path']}")

        # Si se solicitó muestra por comando
        if args.sample:
            dur_req = None
            if args.sample != "auto":
                try:
                    dur_req = float(args.sample)
                except ValueError:
                    dur_req = None
            sample_res = scraper.create_audio_sample(res["mp3_path"], duration_sec=dur_req)
            print(f"✂️ Muestra generada ({sample_res['actual_sample_duration']:.1f}s): {sample_res['sample_path']}")

    except Exception as e:
        print(f"\n❌ Error durante la descarga: {e}")


def launch_gui():
    """Lanza la interfaz gráfica de usuario en Tkinter."""
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    import threading
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.title("Suno AI Song Downloader & Decryptor HQ")
    root.geometry("700x720")
    root.minsize(640, 660)
    root.configure(bg="#121214")

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TProgressbar", thickness=10, troughcolor="#202024", background="#7928CA")
    style.configure("TCombobox", fieldbackground="#202024", background="#29292E", foreground="#FFFFFF")

    scraper = SunoScraper()
    last_audio_file = [None]
    last_sample_file = [None]
    current_duration = [0.0]

    # Header
    header_frame = tk.Frame(root, bg="#1a1a1e", height=70)
    header_frame.pack(fill="x", side="top")
    header_frame.pack_propagate(False)

    lbl_title = tk.Label(
        header_frame,
        text="⚡ SUNO AI DOWNLOADER",
        font=("Segoe UI", 16, "bold"),
        fg="#FF0080",
        bg="#1a1a1e"
    )
    lbl_title.pack(side="left", padx=20, pady=15)

    lbl_sub = tk.Label(
        header_frame,
        text="MP3 Decryptor 320 kbps HQ + Extractor de Muestras",
        font=("Segoe UI", 10, "italic"),
        fg="#888899",
        bg="#1a1a1e"
    )
    lbl_sub.pack(side="left", pady=18)

    # Main Container
    main_frame = tk.Frame(root, bg="#121214")
    main_frame.pack(fill="both", expand=True, padx=20, pady=12)

    # URL Input Section
    lbl_url = tk.Label(
        main_frame,
        text="Pega el enlace compartido de Suno (ej. https://suno.com/song/...):",
        font=("Segoe UI", 10, "bold"),
        fg="#E1E1E6",
        bg="#121214"
    )
    lbl_url.pack(anchor="w", pady=(0, 4))

    url_entry_frame = tk.Frame(main_frame, bg="#202024", bd=1, relief="flat")
    url_entry_frame.pack(fill="x", pady=(0, 10))

    url_entry = tk.Entry(
        url_entry_frame,
        font=("Segoe UI", 11),
        bg="#202024",
        fg="#FFFFFF",
        insertbackground="#FF0080",
        relief="flat"
    )
    url_entry.pack(fill="x", padx=10, pady=8)

    # Options Frame
    opts_frame = tk.Frame(main_frame, bg="#121214")
    opts_frame.pack(fill="x", pady=(0, 8))

    var_cover = tk.BooleanVar(value=True)
    var_meta = tk.BooleanVar(value=True)

    chk_cover = tk.Checkbutton(
        opts_frame, text="Descargar Portada", variable=var_cover,
        bg="#121214", fg="#A8A8B3", selectcolor="#202024", activebackground="#121214",
        activeforeground="#FFFFFF", font=("Segoe UI", 9)
    )
    chk_cover.pack(side="left", padx=(0, 20))

    chk_meta = tk.Checkbutton(
        opts_frame, text="Guardar Letra / Info (.txt)", variable=var_meta,
        bg="#121214", fg="#A8A8B3", selectcolor="#202024", activebackground="#121214",
        activeforeground="#FFFFFF", font=("Segoe UI", 9)
    )
    chk_meta.pack(side="left")

    # Folder Selector Frame
    folder_frame = tk.Frame(main_frame, bg="#121214")
    folder_frame.pack(fill="x", pady=(0, 10))

    lbl_folder_text = tk.Label(
        folder_frame, text="Carpeta de destino:",
        font=("Segoe UI", 9), fg="#A8A8B3", bg="#121214"
    )
    lbl_folder_text.pack(side="left")

    default_dir = os.path.abspath("downloads")
    selected_dir_var = tk.StringVar(value=default_dir)

    lbl_folder_path = tk.Label(
        folder_frame, textvariable=selected_dir_var,
        font=("Segoe UI", 9, "italic"), fg="#00DFD8", bg="#121214"
    )
    lbl_folder_path.pack(side="left", padx=10)

    def choose_directory():
        d = filedialog.askdirectory(initialdir=selected_dir_var.get())
        if d:
            selected_dir_var.set(d)

    btn_browse = tk.Button(
        folder_frame, text="Examinar...", command=choose_directory,
        bg="#29292E", fg="#E1E1E6", relief="flat", font=("Segoe UI", 8, "bold"),
        padx=8, pady=2, cursor="hand2"
    )
    btn_browse.pack(side="right")

    # Progress Section
    progress_bar = ttk.Progressbar(main_frame, style="TProgressbar", mode="determinate")
    progress_bar.pack(fill="x", pady=(0, 4))

    status_var = tk.StringVar(value="Listo. Pega un enlace de Suno y presiona 'Descargar Canción'.")
    lbl_status = tk.Label(
        main_frame, textvariable=status_var,
        font=("Segoe UI", 9), fg="#A8A8B3", bg="#121214"
    )
    lbl_status.pack(anchor="w", pady=(0, 8))

    # Song Info Preview Box
    info_card = tk.Frame(main_frame, bg="#1a1a1e", bd=1, relief="flat")
    info_card.pack(fill="both", expand=True, pady=(0, 10))

    cover_label = tk.Label(info_card, bg="#202024", width=14, height=7, text="[Portada]", fg="#666677")
    cover_label.pack(side="left", padx=12, pady=10)

    details_frame = tk.Frame(info_card, bg="#1a1a1e")
    details_frame.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=10)

    lbl_song_title = tk.Label(
        details_frame, text="Título: --",
        font=("Segoe UI", 11, "bold"), fg="#FFFFFF", bg="#1a1a1e", anchor="w"
    )
    lbl_song_title.pack(fill="x")

    lbl_song_meta = tk.Label(
        details_frame, text="Estilo: -- | Duración: --",
        font=("Segoe UI", 9), fg="#FF0080", bg="#1a1a1e", anchor="w"
    )
    lbl_song_meta.pack(fill="x", pady=(2, 4))

    txt_lyrics = tk.Text(
        details_frame, height=4, font=("Consolas", 8),
        bg="#121214", fg="#CCCCCC", relief="flat", bd=0
    )
    txt_lyrics.pack(fill="both", expand=True)
    txt_lyrics.insert("1.0", "Letra / Prompt aparecerá aquí...")
    txt_lyrics.config(state="disabled")

    # Sample Controls Frame (Muestras de Audio)
    sample_box = tk.LabelFrame(
        main_frame,
        text=" ✂️ DESCARGAR MUESTRA DE AUDIO (PREVIEW) ",
        font=("Segoe UI", 9, "bold"),
        fg="#00DFD8",
        bg="#18181c",
        bd=1,
        relief="groove"
    )
    sample_box.pack(fill="x", pady=(0, 10), padx=2, ipady=4)

    sample_inner = tk.Frame(sample_box, bg="#18181c")
    sample_inner.pack(fill="x", padx=10, pady=4)

    lbl_sample_opt = tk.Label(
        sample_inner,
        text="Duración de la muestra:",
        font=("Segoe UI", 9),
        fg="#E1E1E6",
        bg="#18181c"
    )
    lbl_sample_opt.pack(side="left", padx=(0, 8))

    sample_options = [
        "⚡ 30 Segundos",
        "⏱️ 1 Minuto (60s)",
        "⏳ 2 Minutos (120s)",
        "🌓 Mitad de Canción (50%)",
        "✨ Auto (Recomendada)"
    ]
    sample_choice_var = tk.StringVar(value="✨ Auto (Recomendada)")
    sample_combo = ttk.Combobox(
        sample_inner,
        textvariable=sample_choice_var,
        values=sample_options,
        state="readonly",
        width=24
    )
    sample_combo.pack(side="left", padx=(0, 10))

    def generate_sample_action():
        if not last_audio_file[0] or not os.path.exists(last_audio_file[0]):
            messagebox.showwarning("Primero descarga la canción", "Debes descargar una canción antes de generar una muestra.")
            return

        choice = sample_choice_var.get()
        dur = None
        tot = current_duration[0] or scraper.get_audio_duration(last_audio_file[0])

        if "30" in choice:
            dur = 30.0
        elif "1 Minuto" in choice or "60s" in choice:
            dur = 60.0
        elif "2 Minutos" in choice or "120s" in choice:
            dur = 120.0
        elif "Mitad" in choice:
            dur = max(15.0, tot * 0.5) if tot > 0 else 60.0
        else:
            dur = None  # auto

        status_var.set("Generando muestra de audio en alta calidad con FFmpeg...")
        btn_sample_create.config(state="disabled", text="⏳ Creando...")

        def sample_task():
            try:
                s_res = scraper.create_audio_sample(last_audio_file[0], duration_sec=dur)
                last_sample_file[0] = s_res["sample_path"]
                status_var.set(f"✅ ¡Muestra ({s_res['actual_sample_duration']:.1f}s) guardada con éxito!")
                btn_sample_play.config(state="normal")
                messagebox.showinfo("Muestra Lista", f"Muestra creada con éxito ({s_res['actual_sample_duration']:.1f} segundos):\n\n{os.path.basename(s_res['sample_path'])}\n\nUbicación:\n{s_res['sample_path']}")
            except Exception as e:
                status_var.set(f"❌ Error al crear muestra: {str(e)}")
                messagebox.showerror("Error", f"No se pudo crear la muestra: {str(e)}")
            finally:
                btn_sample_create.config(state="normal", text="✂️ Guardar Muestra MP3")

        threading.Thread(target=sample_task, daemon=True).start()

    btn_sample_create = tk.Button(
        sample_inner,
        text="✂️ Guardar Muestra MP3",
        command=generate_sample_action,
        bg="#00DFD8",
        fg="#000000",
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=3,
        state="disabled",
        cursor="hand2"
    )
    btn_sample_create.pack(side="left", padx=(0, 8))

    def play_sample_audio():
        if last_sample_file[0] and os.path.exists(last_sample_file[0]):
            os.startfile(last_sample_file[0])

    btn_sample_play = tk.Button(
        sample_inner,
        text="▶️ Reproducir Muestra",
        command=play_sample_audio,
        bg="#29292E",
        fg="#00DFD8",
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padx=8,
        pady=3,
        state="disabled",
        cursor="hand2"
    )
    btn_sample_play.pack(side="left")

    # Action Buttons Frame
    btn_frame = tk.Frame(main_frame, bg="#121214")
    btn_frame.pack(fill="x", pady=(4, 0))

    def set_ui_loading(is_loading: bool):
        if is_loading:
            btn_download.config(state="disabled", text="⏳ Descifrando y Descargando...")
            btn_paste.config(state="disabled")
            btn_sample_create.config(state="disabled")
        else:
            btn_download.config(state="normal", text="🚀 DESCARGAR CANCIÓN")
            btn_paste.config(state="normal")
            if last_audio_file[0] and os.path.exists(last_audio_file[0]):
                btn_sample_create.config(state="normal")

    def run_download_thread():
        url = url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL requerida", "Por favor pega el enlace compartido de Suno.")
            return

        set_ui_loading(True)
        progress_bar["value"] = 0
        status_var.set("Conectando y obteniendo licencia de audio...")

        def task():
            try:
                def on_progress(stage, downloaded, total, percent):
                    progress_bar["value"] = percent
                    if total > 0:
                        mb_d = downloaded / (1024 * 1024)
                        mb_t = total / (1024 * 1024)
                        status_var.set(f"[{stage.capitalize()}] {percent:.1f}% ({mb_d:.2f} MB / {mb_t:.2f} MB)")
                    else:
                        status_var.set(f"Procesando: {stage}...")

                res = scraper.download_song(
                    url,
                    output_dir=selected_dir_var.get(),
                    save_cover=var_cover.get(),
                    save_metadata=var_meta.get(),
                    progress_callback=on_progress
                )

                info = res["info"]
                last_audio_file[0] = res["mp3_path"]
                current_duration[0] = res.get("duration", 0.0)

                lbl_song_title.config(text=f"🎵 {info.get('title', 'Suno Track')}")
                dur_m = int(res['duration'] // 60)
                dur_s = int(res['duration'] % 60)
                lbl_song_meta.config(text=f"🏷️ {info.get('tags') or 'Sin estilo'}  |  ⏱️ Duración: {dur_m}:{dur_s:02d}")

                txt_lyrics.config(state="normal")
                txt_lyrics.delete("1.0", "end")
                lyrics_text = info.get("prompt") or "Sin letra disponible."
                txt_lyrics.insert("1.0", lyrics_text)
                txt_lyrics.config(state="disabled")

                if res.get("cover_path") and os.path.exists(res["cover_path"]):
                    try:
                        img = Image.open(res["cover_path"])
                        img = img.resize((100, 100), Image.Resampling.LANCZOS)
                        tk_img = ImageTk.PhotoImage(img)
                        cover_label.config(image=tk_img, text="")
                        cover_label.image = tk_img
                    except Exception:
                        pass

                progress_bar["value"] = 100
                status_var.set(f"✅ ¡MP3 listo para reproducir o recortar muestra! ({os.path.basename(res['mp3_path'])})")
                btn_play.config(state="normal")
                btn_sample_create.config(state="normal")
                messagebox.showinfo("¡Descarga Exitosa!", f"Canción MP3 (320 kbps) lista:\n\n{info.get('title')}\nDuración: {dur_m}:{dur_s:02d}\n\nUbicación:\n{res['mp3_path']}")

            except Exception as e:
                status_var.set(f"❌ Error: {str(e)}")
                messagebox.showerror("Error de Descarga", f"Ocurrió un error al procesar el enlace:\n\n{str(e)}")
            finally:
                set_ui_loading(False)

        threading.Thread(target=task, daemon=True).start()

    def paste_clipboard():
        try:
            cb = root.clipboard_get().strip()
            if cb:
                url_entry.delete(0, tk.END)
                url_entry.insert(0, cb)
        except Exception:
            pass

    btn_paste = tk.Button(
        btn_frame,
        text="📋 Pegar Enlace",
        command=paste_clipboard,
        bg="#29292E",
        fg="#FFFFFF",
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padx=12,
        pady=8,
        cursor="hand2"
    )
    btn_paste.pack(side="left", padx=(0, 10))

    btn_download = tk.Button(
        btn_frame,
        text="🚀 DESCARGAR CANCIÓN",
        command=run_download_thread,
        bg="#7928CA",
        fg="#FFFFFF",
        activebackground="#FF0080",
        activeforeground="#FFFFFF",
        relief="flat",
        font=("Segoe UI", 11, "bold"),
        pady=8,
        cursor="hand2"
    )
    btn_download.pack(side="left", fill="x", expand=True)

    def play_downloaded_audio():
        if last_audio_file[0] and os.path.exists(last_audio_file[0]):
            os.startfile(last_audio_file[0])
        else:
            open_downloads_folder()

    btn_play = tk.Button(
        btn_frame,
        text="▶️ Reproducir MP3",
        command=play_downloaded_audio,
        bg="#00DFD8",
        fg="#000000",
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padx=10,
        pady=8,
        state="disabled",
        cursor="hand2"
    )
    btn_play.pack(side="left", padx=(10, 0))

    def open_downloads_folder():
        folder = selected_dir_var.get()
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    btn_open_folder = tk.Button(
        btn_frame,
        text="📂 Carpeta",
        command=open_downloads_folder,
        bg="#202024",
        fg="#A8A8B3",
        relief="flat",
        font=("Segoe UI", 10),
        padx=10,
        pady=8,
        cursor="hand2"
    )
    btn_open_folder.pack(side="right", padx=(10, 0))

    root.mainloop()


if __name__ == "__main__":
    launch_cli()

