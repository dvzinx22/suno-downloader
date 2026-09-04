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
            "metadata_path": None
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
    parser.add_argument("--gui", action="store_true", help="Abrir interfaz gráfica")

    args = parser.parse_args()

    if args.gui or len(sys.argv) == 1:
        launch_gui()
        return

    if not args.url:
        print("Uso: python suno_downloader.py https://suno.com/song/ID_DE_LA_CANCION")
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
        print(f"🎧 Archivo MP3 (320 kbps): {res['mp3_path']}")
        if res.get('cover_path'):
            print(f"🖼️ Portada: {res['cover_path']}")
        if res.get('metadata_path'):
            print(f"📄 Letra y Metadatos: {res['metadata_path']}")

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
    root.geometry("680x620")
    root.minsize(620, 560)
    root.configure(bg="#121214")

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TProgressbar", thickness=10, troughcolor="#202024", background="#7928CA")

    scraper = SunoScraper()
    last_audio_file = [None]

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
        text="MP3 Decryptor 320 kbps HQ",
        font=("Segoe UI", 10, "italic"),
        fg="#888899",
        bg="#1a1a1e"
    )
    lbl_sub.pack(side="left", pady=18)

    # Main Container
    main_frame = tk.Frame(root, bg="#121214")
    main_frame.pack(fill="both", expand=True, padx=20, pady=15)

    # URL Input Section
    lbl_url = tk.Label(
        main_frame,
        text="Pega el enlace compartido de Suno (ej. https://suno.com/song/...):",
        font=("Segoe UI", 10, "bold"),
        fg="#E1E1E6",
        bg="#121214"
    )
    lbl_url.pack(anchor="w", pady=(0, 5))

    url_entry_frame = tk.Frame(main_frame, bg="#202024", bd=1, relief="flat")
    url_entry_frame.pack(fill="x", pady=(0, 12))

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
    opts_frame.pack(fill="x", pady=(0, 10))

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
    folder_frame.pack(fill="x", pady=(0, 12))

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
    progress_bar.pack(fill="x", pady=(0, 5))

    status_var = tk.StringVar(value="Listo. Pega un enlace de Suno y presiona 'Descargar Canción'.")
    lbl_status = tk.Label(
        main_frame, textvariable=status_var,
        font=("Segoe UI", 9), fg="#A8A8B3", bg="#121214"
    )
    lbl_status.pack(anchor="w", pady=(0, 10))

    # Song Info Preview Box
    info_card = tk.Frame(main_frame, bg="#1a1a1e", bd=1, relief="flat")
    info_card.pack(fill="both", expand=True, pady=(0, 12))

    cover_label = tk.Label(info_card, bg="#202024", width=14, height=7, text="[Portada]", fg="#666677")
    cover_label.pack(side="left", padx=12, pady=12)

    details_frame = tk.Frame(info_card, bg="#1a1a1e")
    details_frame.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=12)

    lbl_song_title = tk.Label(
        details_frame, text="Título: --",
        font=("Segoe UI", 11, "bold"), fg="#FFFFFF", bg="#1a1a1e", anchor="w"
    )
    lbl_song_title.pack(fill="x")

    lbl_song_tags = tk.Label(
        details_frame, text="Estilo: --",
        font=("Segoe UI", 9), fg="#FF0080", bg="#1a1a1e", anchor="w"
    )
    lbl_song_tags.pack(fill="x", pady=(2, 4))

    txt_lyrics = tk.Text(
        details_frame, height=5, font=("Consolas", 8),
        bg="#121214", fg="#CCCCCC", relief="flat", bd=0
    )
    txt_lyrics.pack(fill="both", expand=True)
    txt_lyrics.insert("1.0", "Letra / Prompt aparecerá aquí...")
    txt_lyrics.config(state="disabled")

    # Action Buttons Frame
    btn_frame = tk.Frame(main_frame, bg="#121214")
    btn_frame.pack(fill="x")

    def set_ui_loading(is_loading: bool):
        if is_loading:
            btn_download.config(state="disabled", text="⏳ Descifrando y Descargando...")
            btn_paste.config(state="disabled")
        else:
            btn_download.config(state="normal", text="🚀 DESCARGAR CANCIÓN")
            btn_paste.config(state="normal")

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

                lbl_song_title.config(text=f"🎵 {info.get('title', 'Suno Track')}")
                lbl_song_tags.config(text=f"🏷️ {info.get('tags') or 'Sin estilo especificado'}")

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
                status_var.set(f"✅ ¡MP3 listo para reproducir! ({os.path.basename(res['mp3_path'])})")
                btn_play.config(state="normal")
                messagebox.showinfo("¡Descarga Exitosa!", f"Canción MP3 (320 kbps) lista:\n\n{info.get('title')}\n\nUbicación:\n{res['mp3_path']}")

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
