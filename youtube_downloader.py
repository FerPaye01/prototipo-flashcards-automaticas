import os
import yt_dlp
from typing import Callable, Optional

class YoutubeDownloader:
    """Utilidad para descargar videos de YouTube usando yt-dlp."""
    
    def __init__(self, output_dir: str = "temp_videos"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
    def download_video(self, url: str, progress_callback: Optional[Callable[[str], None]] = None, 
                       use_browser_cookies: bool = False) -> Optional[str]:
        """
        Descarga un video de YouTube y devuelve la ruta al archivo descargado.
        """
        def ydl_progress_hook(d):
            if d['status'] == 'downloading':
                p = d.get('_percent_str', '0%')
                s = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                
                # Intentar distinguir si es video o audio
                info = d.get('info_dict', {}) or {}
                vcodec = info.get('vcodec')
                acodec = info.get('acodec')
                ext = info.get('ext')
                
                stream_type = ""
                if vcodec and vcodec != 'none' and acodec == 'none':
                    stream_type = " (Video)"
                elif acodec and acodec != 'none' and vcodec == 'none':
                    stream_type = " (Audio)"
                elif ext in ['m4a', 'mp3', 'aac', 'opus']:
                    stream_type = " (Audio)"
                    
                if progress_callback:
                    progress_callback(f"📥 Descargando{stream_type}: {p} ({s}, ETA: {eta})")
            elif d['status'] == 'finished':
                info = d.get('info_dict', {}) or {}
                vcodec = info.get('vcodec')
                acodec = info.get('acodec')
                
                stream_type = ""
                if vcodec and vcodec != 'none' and acodec == 'none':
                    stream_type = " (Video)"
                elif acodec and acodec != 'none' and vcodec == 'none':
                    stream_type = " (Audio)"
                    
                if progress_callback:
                    progress_callback(f"✅ Descarga finalizada{stream_type}, procesando archivo...")

        ydl_opts = {
            'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [ydl_progress_hook],
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'socket_timeout': 15,
            'retries': 30,
            'fragment_retries': 30,
            'retry_sleep': 'http=3',
            'add_header': [
                'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language: en-US,en;q=0.5',
                'Referer: https://www.google.com/'
            ]
        }
        
        # Cargar cookies si existen o usar las del navegador
        cookies_path = os.path.join(os.getcwd(), "cookies.txt")
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            if progress_callback:
                progress_callback("🍪 Usando archivo cookies.txt detectado")
        elif use_browser_cookies:
            ydl_opts['cookiesfrombrowser'] = ('chrome', 'firefox', 'opera', 'edge')
            if progress_callback:
                progress_callback("🍪 Intentando extraer cookies del navegador...")
        
        try:
            if progress_callback:
                progress_callback(f"🔍 Analizando video: {url}")
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extraer info
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')
                filename = ydl.prepare_filename(info)
                
                # yt-dlp puede cambiar la extensión al final
                base, _ = os.path.splitext(filename)
                
                # Buscar el archivo resultante real
                possible_extensions = [".mp4", ".mkv", ".webm", ".avi"]
                for ext in possible_extensions:
                    full_path = base + ext
                    if os.path.exists(full_path):
                        return os.path.abspath(full_path)
                
                if os.path.exists(filename):
                    return os.path.abspath(filename)
                
                # Búsqueda final por patrón
                for f in os.listdir(self.output_dir):
                    if f.startswith(title[:15]):
                        return os.path.abspath(os.path.join(self.output_dir, f))
                        
                return None
                    
        except Exception as e:
            error_msg = str(e)
            if "Sign in to confirm you’re not a bot" in error_msg:
                error_msg = "YouTube bloqueó la descarga (Bot detection). Prueba con otro video o usa cookies.txt."
            elif "age restricted" in error_msg.lower():
                error_msg = "Video con restricción de edad. Se requiere cookies.txt."
                
            if progress_callback:
                progress_callback(f"❌ Error: {error_msg}")
            return None

if __name__ == "__main__":
    # Test simple
    downloader = YoutubeDownloader()
    path = downloader.download_video("https://www.youtube.com/watch?v=aqz-KE-bpKQ", print)
    print(f"Resultado: {path}")
