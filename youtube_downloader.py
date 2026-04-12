import os
import yt_dlp
from typing import Callable, Optional

class YoutubeDownloader:
    """Utilidad para descargar videos de YouTube usando yt-dlp."""
    
    def __init__(self, output_dir: str = "temp_videos"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
    def download_video(self, url: str, progress_callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """
        Descarga un video de YouTube y devuelve la ruta al archivo descargado.
        
        Args:
            url: URL del video de YouTube.
            progress_callback: Función para reportar el progreso.
            
        Returns:
            Ruta completa al archivo descargado o None si falla.
        """
        def ydl_progress_hook(d):
            if d['status'] == 'downloading':
                p = d.get('_percent_str', '0%')
                s = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                if progress_callback:
                    progress_callback(f"📥 Descargando: {p} ({s}, ETA: {eta})")
            elif d['status'] == 'finished':
                if progress_callback:
                    progress_callback("✅ Descarga finalizada, procesando archivo...")

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [ydl_progress_hook],
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            if progress_callback:
                progress_callback(f"🔍 Obteniendo información del video: {url}")
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # yt-dlp might change the extension during merging, so we check the actual file
                base, _ = os.path.splitext(filename)
                potential_file = base + ".mp4"
                
                if os.path.exists(potential_file):
                    return os.path.abspath(potential_file)
                elif os.path.exists(filename):
                    return os.path.abspath(filename)
                else:
                    # Search for any file with that base name in the output directory
                    for f in os.listdir(self.output_dir):
                        if f.startswith(os.path.basename(base)):
                            return os.path.abspath(os.path.join(self.output_dir, f))
                    return None
                    
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ Error al descargar de YouTube: {e}")
            return None

if __name__ == "__main__":
    # Test simple
    downloader = YoutubeDownloader()
    path = downloader.download_video("https://www.youtube.com/watch?v=aqz-KE-bpKQ", print)
    print(f"Resultado: {path}")
