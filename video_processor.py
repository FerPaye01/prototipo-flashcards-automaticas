"""
Procesador de videos para extracción de contenido y generación de flashcards.
Soporta segmentación inteligente con Whisper y detección de silencios.
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import shutil

# Gemini API para transcripción multimodal
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

load_dotenv()

# audio_extract para extracción de audio
try:
    from audio_extract import extract_audio
    AUDIO_EXTRACT_AVAILABLE = True
except ImportError:
    AUDIO_EXTRACT_AVAILABLE = False

# imageio para obtener duración del video
try:
    import imageio
    IMAGEIO_AVAILABLE = True
except ImportError:
    IMAGEIO_AVAILABLE = False

# Reproducción multimedia se maneja ahora mediante ffplay o el reproductor del sistema



class VideoSegment:
    """Representa un segmento de audio extraído de un video."""
    
    def __init__(self, start_time: float, end_time: float, segment_id: int):
        self.start_time = start_time  # En segundos
        self.end_time = end_time
        self.segment_id = segment_id
        self.duration = end_time - start_time
        self.audio_path = None  # Ruta al archivo de audio MP3
        self.transcription_path = None  # Ruta al archivo .txt con transcripción
        self.transcription_text = ""  # Texto de la transcripción
        self.char_count = 0  # Número de caracteres
        self.section_id = None  # ID de la sección a la que pertenece (None si no está asignado)
    
    def get_time_range_str(self) -> str:
        """Retorna el rango de tiempo formateado."""
        start_min = int(self.start_time // 60)
        start_sec = int(self.start_time % 60)
        end_min = int(self.end_time // 60)
        end_sec = int(self.end_time % 60)
        return f"{start_min}:{start_sec:02d}-{end_min}:{end_sec:02d}"
    
    def __repr__(self):
        return f"Segment {self.segment_id}: {self.get_time_range_str()} ({self.duration:.1f}s, {self.char_count} chars)"


class VideoSection:
    """Representa una sección que agrupa múltiples segmentos de video."""
    
    def __init__(self, section_id: int):
        self.section_id = section_id
        self.title = f"Sección {section_id}"
        self.segments = []  # Lista de VideoSegment
    
    def add_segment(self, segment: VideoSegment):
        """Añade un segmento a la sección."""
        if len(self.segments) >= 10:
            return False  # Límite de 10 transcripciones por sección
        segment.section_id = self.section_id
        self.segments.append(segment)
        return True
    
    def remove_segment(self, segment: VideoSegment):
        """Elimina un segmento de la sección."""
        if segment in self.segments:
            segment.section_id = None
            self.segments.remove(segment)
    
    def get_total_chars(self) -> int:
        """Retorna el total de caracteres de todos los segmentos."""
        return sum(seg.char_count for seg in self.segments)
    
    def get_segment_count(self) -> int:
        """Retorna el número de segmentos."""
        return len(self.segments)
    
    def get_transcription_paths(self) -> List[str]:
        """Retorna las rutas de los archivos de transcripción."""
        return [seg.transcription_path for seg in self.segments if seg.transcription_path]
    
    def __repr__(self):
        return f"Section {self.section_id}: {len(self.segments)} segments, {self.get_total_chars()} chars"


class VideoProcessor:
    """Procesador de videos con segmentación inteligente."""
    
    # Límites (temporalmente aumentados o eliminados)
    MAX_DURATION = 36000  # 10 horas en segundos (aumentado)
    MAX_SIZE = 10 * 1024 * 1024 * 1024  # 10GB (aumentado)
    SUPPORTED_FORMATS = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.mov', 
                         '.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus')
    
    # Directorio temporal
    TEMP_DIR = os.path.join("Flashcards Programa", "temp_videos")
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """Inicializa el procesador."""
        self.log_callback = log_callback or print
        self._ensure_temp_dir()
        
        # Verificar disponibilidad de FFmpeg
        self.ffmpeg_available = self._check_ffmpeg()
        if not self.ffmpeg_available:
            self._log("⚠️ ADVERTENCIA: FFmpeg no encontrado en el sistema. La extracción de video/audio fallará.")
            self._log("   Instala FFmpeg y asegúrate de que esté en tu PATH.")

        # Cargar pool de llaves (Misma lógica centralizada)
        kstr = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEYS_OCR")
        if kstr:
            self.api_keys = [k.strip() for k in kstr.split(",") if k.strip()]
        else:
            # Fallback a llaves individuales para compatibilidad
            self.api_keys = []
            for i in range(1, 5):
                k = os.environ.get(f"GEMINI_API_KEY_{i}") or os.environ.get(f"GEMINI_API_KEYS_{i}")
                if k: self.api_keys.extend([x.strip() for x in k.split(",") if x.strip()])
            
        # Cargar pool de modelos
        mstr = os.environ.get("GEMINI_MODEL") or "gemini-1.5-flash"
        self.models_pool = [m.strip() for m in mstr.split(",") if m.strip()]
        
        self.current_key_index = 0
        self.exhausted_keys = set()

    def _check_ffmpeg(self) -> bool:
        """Verifica si ffmpeg está instalado."""
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except FileNotFoundError:
            return False
    
    def _log(self, message: str):
        """Registra un mensaje."""
        if self.log_callback:
            self.log_callback(message)
    
    def _ensure_temp_dir(self):
        """Asegura que existe el directorio temporal."""
        if not os.path.exists(self.TEMP_DIR):
            os.makedirs(self.TEMP_DIR)
    
    def validate_video(self, video_path: str) -> tuple[bool, str]:
        """
        Valida que el video cumpla con los requisitos.
        
        Returns:
            (válido, mensaje)
        """
        if not os.path.exists(video_path):
            return False, "El archivo no existe"
        
        # Verificar extensión
        ext = os.path.splitext(video_path)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            return False, f"Formato no soportado. Use: {', '.join(self.SUPPORTED_FORMATS)}"
        
        media_label = "Audio" if ext in ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus') else "Video"
        
        # Verificar tamaño
        size = os.path.getsize(video_path)
        size_mb = size / (1024 * 1024)
        if size > self.MAX_SIZE:
            return False, f"Archivo muy grande ({size_mb:.1f} MB). Máximo: {self.MAX_SIZE / (1024*1024*1024):.0f}GB"
        
        # Obtener duración real del video
        duration = self._get_video_duration(video_path)
        
        if duration is None:
            self._log(f"⚠️ No se pudo obtener duración, procesando de todos modos")
            return True, f"{media_label} válido (tamaño: {size_mb:.1f} MB)"
        
        duration_min = duration / 60
        
        if duration > self.MAX_DURATION:
            return False, f"{media_label} muy largo ({duration_min:.1f} min). Máximo: {self.MAX_DURATION / 3600:.0f} horas"
        
        return True, f"{media_label} válido ({duration_min:.1f} min, {size_mb:.1f} MB)"
    
    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """
        Obtiene la duración real del video usando múltiples métodos.
        
        Returns:
            Duración en segundos o None si no se puede obtener
        """
        # Método 1: Usar imageio
        if IMAGEIO_AVAILABLE:
            try:
                reader = imageio.get_reader(video_path)
                duration = reader.get_meta_data().get('duration', 0)
                reader.close()
                if duration > 0:
                    return duration
            except Exception as e:
                self._log(f"⚠️ imageio no pudo leer duración: {e}")
        
        # Método 2: Usar mutagen (si está disponible)
        try:
            import mutagen
            file = mutagen.File(video_path)
            if file is not None and hasattr(file, 'info') and hasattr(file.info, 'length'):
                duration = file.info.length
                if duration > 0:
                    return duration
        except Exception as e:
            self._log(f"⚠️ mutagen no pudo leer duración: {e}")
            
        # Método 3: Usar audio_extract con el video completo
        if AUDIO_EXTRACT_AVAILABLE:
            try:
                import tempfile
                import wave
                
                self._ensure_temp_dir()
                # Extraer audio completo para obtener duración
                with tempfile.NamedTemporaryFile(suffix='.wav', dir=self.TEMP_DIR, delete=False) as tmp:
                    tmp_path = tmp.name
                
                extract_audio(
                    input_path=video_path,
                    output_path=tmp_path,
                    output_format='wav',
                    overwrite=True
                )
                
                if os.path.exists(tmp_path):
                    with wave.open(tmp_path, 'rb') as wav_file:
                        frames = wav_file.getnframes()
                        rate = wav_file.getframerate()
                        duration = frames / rate
                    
                    # Intentar eliminar, pero no fallar si Windows lo tiene bloqueado
                    try:
                        import time
                        time.sleep(0.1) # Pequeña pausa para permitir que Windows libere el handle
                        os.remove(tmp_path)
                    except Exception as removal_error:
                        self._log(f"⚠️ No se pudo eliminar el archivo temporal {tmp_path}: {removal_error}")
                    
                    return duration
            except Exception as e:
                self._log(f"⚠️ audio_extract no pudo obtener duración: {e}")
        
        # Método 3: Estimar por tamaño (fallback)
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        estimated_duration = size_mb * 60  # ~1 minuto por MB
        self._log(f"⚠️ Usando duración estimada: {estimated_duration/60:.1f} min")
        return estimated_duration
    
    def _get_gemini_client(self):
        """Devuelve el cliente Gemini usando la API Key actual."""
        if not self.api_keys:
            return genai.Client()
        return genai.Client(api_key=self.api_keys[self.current_key_index])

    def _upload_file_with_retry(self, client, file_path: str, max_retries: int = 5, initial_delay: float = 2.0):
        """Sube un archivo a Gemini con reintentos para fallas de red."""
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                return client.files.upload(file=file_path)
            except Exception as e:
                last_exception = e
                error_str = str(e)
                # Detectar errores comunes de conexión (incluyendo 10054)
                is_connection_error = any(msg in error_str.lower() for msg in [
                    "connection", "10054", "reset", "broken pipe", "timeout", "network"
                ])
                
                if is_connection_error:
                    remaining = max_retries - attempt - 1
                    if remaining > 0:
                        self._log(f"   ⚠️ Error de conexión al subir ({error_str}). Reintentando en {delay}s... ({remaining} intentos restantes)")
                        time.sleep(delay)
                        delay *= 2  # Backoff exponencial
                        continue
                
                # Si no es un error de conexión conocido o no quedan intentos, propagar
                self._log(f"   ❌ Error crítico subiendo a Gemini: {e}")
                raise e
        
        raise last_exception

    def _rotate_api_key(self) -> bool:
        """Rota a la siguiente API key. Retorna True si rotó, False si dio la vuelta."""
        if not self.api_keys:
            return False
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return self.current_key_index != 0

    def _generate_with_fallback(self, file_obj, prompt: str) -> str:
        """Genera contenido usando el pool de modelos con reintentos por rate limit.
        
        IMPORTANTE: Los archivos subidos a Gemini están vinculados a la API Key
        que los subió. NO se puede rotar a otra key para acceder al mismo archivo.
        """
        max_retries = 3  # Reintentos por rate limit por modelo
        
        for model_name in self.models_pool:
            self._log(f"   🤖 Intentando con modelo {model_name}...")
            
            for attempt in range(max_retries):
                client = self._get_gemini_client()
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[file_obj, prompt],
                        config=types.GenerateContentConfig(temperature=0.1)
                    )
                    return response.text
                except Exception as e:
                    error_str = str(e).lower()
                    
                    if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                        wait_time = 30 * (attempt + 1)
                        if attempt < max_retries - 1:
                            self._log(f"   ⏳ Rate limit en {model_name}. Esperando {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self._log(f"   ⚠️ Modelo {model_name} agotado tras {max_retries} intentos. Probando siguiente modelo...")
                            break 
                    elif "permission_denied" in error_str or "403" in error_str:
                        self._log(f"   ❌ Permiso denegado (archivo no accesible con esta key).")
                        break
                    else:
                        self._log(f"   ❌ Error de Gemini ({model_name}): {e}")
                        break
        
        raise Exception("No se pudo generar contenido tras agotar el pool de modelos.")
    
    def segment_by_fixed_duration(
        self,
        video_duration: float,
        segment_duration: float = 180,
        overlap: float = 30
    ) -> List[VideoSegment]:
        """
        Segmenta el video en intervalos fijos con overlap.
        
        Args:
            video_duration: Duración total del video en segundos
            segment_duration: Duración de cada segmento en segundos
            overlap: Overlap entre segmentos en segundos
            
        Returns:
            Lista de VideoSegment
        """
        segments = []
        segment_id = 1
        current_time = 0
        
        while current_time < video_duration:
            start_time = max(0, current_time - overlap) if segment_id > 1 else 0
            end_time = min(current_time + segment_duration, video_duration)
            
            segment = VideoSegment(start_time, end_time, segment_id)
            segments.append(segment)
            
            current_time += segment_duration
            segment_id += 1
        
        self._log(f"📊 Segmentación fija: {len(segments)} segmentos de ~{segment_duration}s")
        return segments
    
    def segment_by_silence(
        self,
        video_path: str,
        min_silence_duration: float = 1.0,
        silence_threshold: int = -40
    ) -> List[float]:
        """
        Detecta silencios en el audio para determinar puntos de corte.
        
        Args:
            video_path: Ruta al video
            min_silence_duration: Duración mínima de silencio en segundos
            silence_threshold: Umbral de silencio en dB
            
        Returns:
            Lista de timestamps donde hay silencios
        """
        self._log("🔇 Detectando silencios en audio...")
        
        try:
            # Usar ffmpeg para detectar silencios
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-af', f'silencedetect=noise={silence_threshold}dB:d={min_silence_duration}',
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stderr=subprocess.STDOUT
            )
            
            # Parsear output para encontrar timestamps de silencios
            silence_times = []
            for line in result.stdout.split('\n'):
                if 'silence_end' in line:
                    # Extraer timestamp
                    parts = line.split('silence_end: ')
                    if len(parts) > 1:
                        time_str = parts[1].split('|')[0].strip()
                        try:
                            silence_times.append(float(time_str))
                        except:
                            pass
            
            self._log(f"✅ Detectados {len(silence_times)} silencios")
            return silence_times
        
        except Exception as e:
            self._log(f"⚠️ Error detectando silencios: {e}")
            return []
    
    def segment_by_transcription_analysis(
        self,
        transcription: Dict[str, Any],
        max_segment_duration: float = 180
    ) -> List[float]:
        """
        Analiza la transcripción para encontrar cambios de tema.
        
        Args:
            transcription: Resultado de Whisper
            max_segment_duration: Duración máxima de segmento
            
        Returns:
            Lista de timestamps sugeridos para cortes
        """
        self._log("📝 Analizando transcripción para detectar cambios de tema...")
        
        # Por ahora, usar los segmentos de Whisper como guía
        # En el futuro, se puede usar Gemini para análisis semántico
        
        cut_points = []
        
        if 'segments' in transcription:
            current_time = 0
            
            for segment in transcription['segments']:
                segment_start = segment['start']
                
                # Si ha pasado suficiente tiempo, marcar como punto de corte
                if segment_start - current_time >= max_segment_duration:
                    cut_points.append(segment_start)
                    current_time = segment_start
        
        self._log(f"✅ Identificados {len(cut_points)} puntos de corte por tema")
        return cut_points
    
    def merge_cut_points(
        self,
        fixed_cuts: List[float],
        silence_cuts: List[float],
        transcription_cuts: List[float],
        tolerance: float = 5.0
    ) -> List[float]:
        """
        Combina múltiples fuentes de puntos de corte.
        
        Args:
            fixed_cuts: Cortes fijos
            silence_cuts: Cortes por silencio
            transcription_cuts: Cortes por análisis de transcripción
            tolerance: Tolerancia para considerar puntos cercanos como iguales
            
        Returns:
            Lista unificada de puntos de corte
        """
        all_cuts = sorted(set(fixed_cuts + silence_cuts + transcription_cuts))
        
        # Eliminar puntos muy cercanos
        merged = []
        for cut in all_cuts:
            if not merged or cut - merged[-1] > tolerance:
                merged.append(cut)
        
        return merged
    
    def create_segments_from_cuts(
        self,
        cut_points: List[float],
        video_duration: float
    ) -> List[VideoSegment]:
        """
        Crea objetos VideoSegment a partir de puntos de corte.
        
        Args:
            cut_points: Lista de timestamps de corte
            video_duration: Duración total del video
            
        Returns:
            Lista de VideoSegment
        """
        segments = []
        cut_points = [0] + sorted(cut_points) + [video_duration]
        
        for i in range(len(cut_points) - 1):
            segment = VideoSegment(
                start_time=cut_points[i],
                end_time=cut_points[i + 1],
                segment_id=i + 1
            )
            segments.append(segment)
        
        return segments
    
    def extract_video_segment(
        self,
        video_path: str,
        segment: VideoSegment,
        output_dir: str
    ) -> str:
        """
        Extrae un chunk de video (MP4) o audio (WAV) usando ffmpeg.
        Para archivos de audio puro, extrae como WAV en lugar de MP4.
        """
        if not self.ffmpeg_available:
            self._log(f"❌ Error: FFmpeg no está disponible. No se puede extraer el segmento {segment.segment_id}.")
            return None

        # Detectar si es audio puro
        source_ext = os.path.splitext(video_path)[1].lower()
        is_audio_source = source_ext in ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus')
        
        if is_audio_source:
            output_ext = ".wav"
        else:
            output_ext = ".mp4"
        
        output_path = os.path.join(
            output_dir,
            f"segment_{segment.segment_id:03d}{output_ext}"
        )
        
        try:
            # Calcular tiempo de inicio en formato HH:MM:SS
            start_time = str(int(segment.start_time // 3600)).zfill(2) + ":" + \
                        str(int((segment.start_time % 3600) // 60)).zfill(2) + ":" + \
                        str(int(segment.start_time % 60)).zfill(2)
            
            if is_audio_source:
                # Para audio: extraer como WAV (PCM) para máxima compatibilidad con Gemini
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', video_path,
                    '-ss', start_time,
                    '-t', str(segment.duration),
                    '-vn',  # Sin video
                    '-acodec', 'pcm_s16le',  # PCM 16-bit
                    '-ar', '16000',  # 16kHz (óptimo para speech)
                    '-ac', '1',  # Mono
                    output_path
                ]
            else:
                # Para video: copia directa de streams
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', video_path,
                    '-ss', start_time,
                    '-t', str(segment.duration),
                    '-c', 'copy',
                    output_path
                ]
            
            self._log(f"   🎬 Ejecutando FFmpeg para segmento {segment.segment_id}...")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                self._log(f"❌ Error de FFmpeg (Código {result.returncode}): {result.stderr[-200:]}")
                return None
            
            if os.path.exists(output_path):
                segment.audio_path = output_path
                self._log(f"      ✅ Segmento {segment.segment_id} extraído exitosamente.")
                return output_path
            else:
                self._log(f"❌ No se encontró el archivo de salida tras ejecutar FFmpeg para el segmento {segment.segment_id}")
                return None
        
        except Exception as e:
            self._log(f"❌ Excepción durante extracción de segmento {segment.segment_id}: {e}")
            return None
    
    def transcribe_video_segment(
        self,
        segment: VideoSegment,
        language: str = "es",
        pre_uploaded_file=None,
        skip_cleanup: bool = False,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe un segmento de video completo usando Gemini Multimodal.
        
        Args:
            segment: VideoSegment con audio_path (ahora es un MP4)
            language: Código de idioma (Omitido para Gemini, que detecta automático)
            pre_uploaded_file: Objeto de archivo de Gemini si ya se subió y procesó previamente
            skip_cleanup: Si es True, no elimina el archivo de la API después de transcribir
            custom_prompt: Prompt personalizado opcional para la transcripción
            
        Returns:
            Texto de la transcripción
        """
        if not pre_uploaded_file and (not segment.audio_path or not os.path.exists(segment.audio_path)):
            self._log(f"❌ No se encontró video para segmento {segment.segment_id}")
            return ""
        
        try:
            client = self._get_gemini_client()
            
            if pre_uploaded_file:
                myfile = pre_uploaded_file
            else:
                self._log(f"   ⬆ Subiendo a Gemini: {os.path.basename(segment.audio_path)}...")
                myfile = self._upload_file_with_retry(client, segment.audio_path)
                
                self._log(f"   ⏳ Esperando procesamiento en la nube...")
                while myfile.state.name == "PROCESSING":
                    time.sleep(3)
                    myfile = client.files.get(name=myfile.name)
                    
                if myfile.state.name == "FAILED":
                    self._log(f"   ❌ Falla en servidor de Gemini.")
                    return ""
            
            # Determinar prompt
            if custom_prompt:
                prompt = custom_prompt
            else:
                is_audio = segment.audio_path.lower().endswith(('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus'))
                if is_audio:
                    prompt = self.DEFAULT_SEGMENT_AUDIO_PROMPT
                else:
                    prompt = self.DEFAULT_SEGMENT_VIDEO_PROMPT
            
            self._log(f"   🧠 Generando transcripción multimodal...")
            transcription_text = self._generate_with_fallback(myfile, prompt)
            transcription_text = transcription_text.strip() if transcription_text else ""
            
            segment.transcription_text = transcription_text
            segment.char_count = len(transcription_text)
            
            # Limpiar archivo de la API por sanidad (si no se omite)
            if not skip_cleanup:
                try:
                    client.files.delete(name=myfile.name)
                except Exception:
                    pass
                
            return transcription_text
        
        except Exception as e:
            self._log(f"❌ Error transcribiendo segmento {segment.segment_id}: {e}")
            return ""
    
    def save_transcription_to_file(
        self,
        segment: VideoSegment,
        output_dir: str
    ) -> str:
        """
        Guarda la transcripción de un segmento en un archivo .txt.
        
        Args:
            segment: VideoSegment con transcription_text
            output_dir: Directorio de salida
            
        Returns:
            Ruta al archivo .txt
        """
        output_path = os.path.join(
            output_dir,
            f"transcription_{segment.segment_id:03d}.txt"
        )
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Escribir metadata como comentario
                f.write(f"# Segmento {segment.segment_id}\n")
                f.write(f"# Tiempo: {segment.get_time_range_str()}\n")
                f.write(f"# Duración: {segment.duration:.1f}s\n")
                f.write(f"# Caracteres: {segment.char_count}\n")
                f.write("\n")
                f.write(segment.transcription_text)
            
            segment.transcription_path = output_path
            return output_path
        
        except Exception as e:
            self._log(f"❌ Error guardando transcripción del segmento {segment.segment_id}: {e}")
            return None
    
    def process_video(
        self,
        video_path: str,
        segment_duration: float = 180,
        overlap: float = 30,
        use_silence_detection: bool = False,
        use_transcription_analysis: bool = True,
        language: str = "es",
        model_size: str = "base",
        on_segment_complete: Optional[Callable[["VideoSegment"], None]] = None,
        great_grandparent: str = "",
        grandparent: str = "",
        father_prefix: str = "",
        extraction_mode: str = "Transcripción Estándar",
        explicit_timestamps: Optional[List[Dict[str, float]]] = None
    ) -> Dict[str, Any]:
        """
        Procesa un video completo: valida, segmenta, extrae audio y transcribe.
        """
        if not self.ffmpeg_available:
            self._log("\n" + "!"*60)
            self._log("❌ ERROR CRÍTICO: FFmpeg no está instalado o no se encuentra en el PATH.")
            self._log("   La extracción de segmentos de video es IMPOSIBLE sin FFmpeg.")
            self._log("   Instálalo con 'winget install ffmpeg' y reinicia la aplicación.")
            self._log("!"*60 + "\n")
            return {"success": False, "error": "FFmpeg missing"}

        is_audio_file = video_path.lower().endswith(('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus'))
        media_label = "AUDIO" if is_audio_file else "VIDEO"
        media_icon = "🎵" if is_audio_file else "🎬"
        
        self._log(f"\n{'='*60}")
        self._log(f"{media_icon} PROCESANDO {media_label}")
        self._log(f"{'='*60}")
        media_icon = "🎧" if is_audio_file else "🎬"
        
        self._log("\n" + "="*60)
        self._log(f"{media_icon} PROCESANDO {media_label}")
        self._log("="*60)
        
        # 1. Validar video
        valid, msg = self.validate_video(video_path)
        if not valid:
            self._log(f"❌ {msg}")
            return {"success": False, "error": msg}
        
        self._log(f"✅ {msg}")
        
        # 2. Obtener duración
        try:
            video_duration = self._get_video_duration(video_path)
            if video_duration is None:
                video_duration = os.path.getsize(video_path) / (1024 * 1024) * 60
                self._log("⚠️ Usando estimación de duración debido a fallo en lectura")
                
        except Exception as e:
            return {"success": False, "error": f"No se pudo obtener duración del video: {e}"}
        
        # 3. Crear sesión temporal
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(self.TEMP_DIR, f"session_{session_id}")
        video_chunks_dir = os.path.join(session_dir, "video_chunks")
        transcriptions_dir = os.path.join(session_dir, "transcriptions")
        os.makedirs(video_chunks_dir, exist_ok=True)
        os.makedirs(transcriptions_dir, exist_ok=True)
        
        # 4. Determinar puntos de corte
        if explicit_timestamps:
            self._log(f"\n✂️ Usando {len(explicit_timestamps)} cortes semánticos explícitos proporcionados por IA...")
            segments = []
            for i, ts in enumerate(explicit_timestamps):
                segment = VideoSegment(
                    start_time=ts["start"],
                    end_time=ts["end"],
                    segment_id=i + 1
                )
                segments.append(segment)
        else:
            self._log(f"\n✂️ Segmentando {media_label.lower()} de forma estándar...")
            self._log(f"   Duración del segmento: {segment_duration}s")
            self._log(f"   Overlap: {overlap}s")
            
            segments = self.segment_by_fixed_duration(
                video_duration, segment_duration, overlap
            )
        
        
        self._log(f"   Total de segmentos: {len(segments)}")
        
        # 5. Extraer trozos
        extract_fmt = "WAV" if is_audio_file else "MP4"
        self._log(f"\n{media_icon} Extrayendo cortes de {media_label.lower()} ({extract_fmt})...")
        
        for i, segment in enumerate(segments, 1):
            self._log(f"   [{i}/{len(segments)}] Segmento {segment.segment_id}: {segment.get_time_range_str()}")
            self.extract_video_segment(video_path, segment, video_chunks_dir)
            
            # Log de tamaño según los requisitos en la interfaz
            if segment.audio_path and os.path.exists(segment.audio_path):
                size_mb = os.path.getsize(segment.audio_path) / (1024 * 1024)
                self._log(f"      📦 Tamaño: {size_mb:.2f} MB - Duración: {segment.duration}s")
        
        # Si el modo es Generación Directa, terminamos aquí para evitar gastos y tiempos de API.
        # Las flashcards se generarán en caliente después.
        if extraction_mode == "Generación Directa (Multimodal)":
            self._log(f"\n⚡ Modo Generación Directa detectado. Saltando fases de transcripción multimodal.")
            self._log(f"   (Los fragmentos de {media_label.lower()} serán enviados directamente a Gemini al crear secciones).")
            
            # Guardar metadata de la sesión para poder recuperarla si la app se cierra
            metadata = {
                "session_id": session_id,
                "original_video": os.path.basename(video_path),
                "video_path": video_path,
                "duration": video_duration,
                "language": language,
                "great_grandparent": great_grandparent,
                "grandparent": grandparent,
                "father_prefix": father_prefix,
                "segment_duration": segment_duration,
                "overlap": overlap,
                "total_segments": len(segments),
                "extraction_mode": extraction_mode,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "segments": [
                    {
                        "id": s.segment_id,
                        "start": s.start_time,
                        "end": s.end_time,
                        "duration": s.duration,
                        "time_range": s.get_time_range_str(),
                        "audio_file": os.path.basename(s.audio_path) if s.audio_path else None,
                        "transcription_file": None,
                        "char_count": 0
                    }
                    for s in segments
                ]
            }
            metadata_path = os.path.join(session_dir, "metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            self._log(f"   💾 Sesión temporal guardada en: {session_dir}")
            
            return {
                "success": True,
                "session_id": session_id,
                "session_dir": session_dir,
                "video_chunks_dir": video_chunks_dir,
                "segments": segments,
                "total_chars": 0
            }


        # 6. Fase 1: Subir todos los segmentos
        self._log(f"\n⬆️ [Fase 1] Subiendo {len(segments)} recortes de {media_label.lower()} a Gemini...")
        client = self._get_gemini_client()
        uploaded_files = {}
        for i, segment in enumerate(segments, 1):
            if segment.audio_path and os.path.exists(segment.audio_path):
                self._log(f"   [{i}/{len(segments)}] Subiendo segmento {segment.segment_id}...")
                try:
                    myfile = self._upload_file_with_retry(client, segment.audio_path)
                    uploaded_files[segment.segment_id] = myfile
                except Exception as e:
                    self._log(f"   ❌ Error subiendo segmento {segment.segment_id}: {e}")
        
        # Fase 2: Esperar procesamiento de todos los archivos en los servidores de Google
        self._log(f"\n⏳ [Fase 2] Esperando que Google procese los archivos (Estado ACTIVE)...")
        for seg_id, myfile in uploaded_files.items():
            while myfile.state.name == "PROCESSING":
                time.sleep(3)
                myfile = client.files.get(name=myfile.name)
                uploaded_files[seg_id] = myfile
            
            if myfile.state.name == "FAILED":
                self._log(f"   ❌ Falla en servidor de Gemini para segmento {seg_id}.")
            else:
                self._log(f"   ✅ Segmento {seg_id} procesado y listo.")
                
        # Fase 3: Transcribir cada segmento secuencialmente (evita colisiones de rate limit)
        self._log(f"\n📝 [Fase 3] Transcribiendo {len(segments)} segmentos con Gemini Multimodal (secuencial)...")
        
        total_chars = 0
        for i, seg in enumerate(segments, 1):
            myfile = uploaded_files.get(seg.segment_id)
            if not myfile or myfile.state.name == "FAILED":
                self._log(f"   ⚠️ Saltando segmento {seg.segment_id} (No subido o Fallido)")
                continue
                
            self._log(f"\n   [{i}/{len(segments)}] Transcribiendo segmento {seg.segment_id}...")
            trans_text = self.transcribe_video_segment(
                segment=seg, 
                language=language, 
                pre_uploaded_file=myfile, 
                skip_cleanup=True
            )
            if trans_text:
                self.save_transcription_to_file(seg, transcriptions_dir)
                # Notificar al caller para guardado incremental
                if on_segment_complete:
                    try:
                        on_segment_complete(seg)
                    except Exception as cb_err:
                        self._log(f"   ⚠️ Error en callback de guardado incremental: {cb_err}")
                self._log(f"      ✅ Segmento {seg.segment_id} transcrito: {seg.char_count} caracteres")
            else:
                self._log(f"      ⚠️ Segmento {seg.segment_id} sin transcripción")
            
            # Cooldown entre segmentos para respetar rate limits (15s)
            if i < len(segments):
                self._log(f"   ⏳ Cooldown de 15s antes del siguiente segmento...")
                time.sleep(15)
                
        # Fase 4: Limpieza de la API
        self._log(f"\n🧹 [Fase 4] Limpiando archivos temporales en los servidores de Google...")
        for seg_id, myfile in uploaded_files.items():
            try:
                client.files.delete(name=myfile.name)
            except Exception:
                pass
        
        # 7. Guardar metadata de la sesión
        metadata = {
            "session_id": session_id,
            "original_video": os.path.basename(video_path),
            "video_path": video_path,
            "duration": video_duration,
            "language": language,
            "great_grandparent": great_grandparent,
            "grandparent": grandparent,
            "father_prefix": father_prefix,
            "segment_duration": segment_duration,
            "overlap": overlap,
            "total_segments": len(segments),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "segments": [
                {
                    "id": s.segment_id,
                    "start": s.start_time,
                    "end": s.end_time,
                    "duration": s.duration,
                    "time_range": s.get_time_range_str(),
                    "audio_file": os.path.basename(s.audio_path) if s.audio_path else None,
                    "transcription_file": os.path.basename(s.transcription_path) if s.transcription_path else None,
                    "char_count": s.char_count
                }
                for s in segments
            ]
        }
        
        metadata_path = os.path.join(session_dir, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        self._log("\n✅ Procesamiento completado")
        self._log(f"   📁 Sesión guardada en: {session_dir}")
        self._log(f"   🎵 {len(segments)} archivos de video (MP4)")
        self._log(f"   📝 {len(segments)} transcripciones")
        total_chars = sum(s.char_count for s in segments)
        self._log(f"   📊 Total de caracteres: {total_chars:,}")
        self._log("="*60 + "\n")
        
        return {
            "success": True,
            "session_id": session_id,
            "session_dir": session_dir,
            "video_chunks_dir": video_chunks_dir,
            "transcriptions_dir": transcriptions_dir,
            "segments": segments,

            "metadata": metadata,
            "total_chars": total_chars
        }
    
    def play_audio(self, media_path: str):
        """
        Reproduce un archivo multimedia (audio o video) usando el reproductor del sistema o ffplay.
        
        Args:
            media_path: Ruta al archivo de audio o video
        """
        if not os.path.exists(media_path):
            self._log(f"❌ Archivo no encontrado: {media_path}")
            return
        
        try:
            self._log(f"▶️ Reproduciendo: {os.path.basename(media_path)}")
            import sys
            
            is_audio = media_path.lower().endswith(('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus'))
            
            def _play_system_default(path):
                if sys.platform.startswith('darwin'):
                    subprocess.call(('open', path))
                elif os.name == 'nt':
                    os.startfile(path)
                elif os.name == 'posix':
                    subprocess.call(('xdg-open', path))
            
            if is_audio:
                # Usar ffplay para audios sin mostrar pantalla y bloquear ejecución
                cmd = ['ffplay', '-autoexit', '-nodisp', '-loglevel', 'quiet', media_path]
                try:
                    subprocess.run(cmd, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self._log(f"⚠️ ffplay falló. Intentando reproductor del sistema...")
                    _play_system_default(media_path)
            else:
                # Para videos usar reproductor por defecto del sistema (VLC, Películas, etc.) para tener controles UI
                self._log(f"🎬 Abriendo video en reproductor del sistema con controles completos...")
                _play_system_default(media_path)
                
            self._log(f"⏹️ Acción de reproducción finalizada")
                
        except Exception as e:
            self._log(f"❌ Error reproduciendo: {e}")
    
    def cleanup_session(self, session_dir: str):
        """Elimina los archivos temporales de una sesión."""
        try:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                self._log(f"🗑️ Sesión limpiada: {os.path.basename(session_dir)}")
        except Exception as e:
            self._log(f"⚠️ Error limpiando sesión: {e}")

    # =========================================================================
    # TRANSCRIPCIÓN FIEL PARA FUENTE DE CONSULTA
    # =========================================================================

    DEFAULT_SEGMENT_AUDIO_PROMPT = (
        "Actúa como un excelente estudiante universitario especializado, elaborando "
        "material de estudio integral basado en el contenido de AUDIO proporcionado. "
        "Tu instrucción ESTRICTA es integrar y consolidar paso a paso todo el conocimiento verbal, "
        "explicaciones exactas, ejemplos mencionados y matices del ponente. "
        "Debes añadir observaciones y apuntes complementarios como un estudiante brillante resaltando "
        "lo relevante del contenido, todo con la mejor ortografía y puntuación posibles en español. "
        "ESTÁ ESTRICTAMENTE PROHIBIDO SIMPLIFICAR O RESUMIR; no debes perder información sin importar "
        "qué tan largo sea. Debes recuperar hasta el último detalle técnico válido mencionado. "
        "ADICIONALMENTE: Si se dictan fragmentos de CÓDIGO o ESPECIFICACIONES TÉCNICAS, debes recrearlos "
        "ÍNTEGRAMENTE. Si es una REUNIÓN o ENTREVISTA, identifica claramente participantes, acuerdos y decisiones."
    )

    DEFAULT_SEGMENT_VIDEO_PROMPT = (
        "Actúa como un excelente estudiante universitario especializado, elaborando "
        "material de estudio integral basado en el contenido audiovisual proporcionado.\n"
        "Recibes la imagen del video de manera sincronizada con la voz. Tu instrucción ESTRICTA "
        "es integrar y consolidar paso a paso todo el conocimiento visual y verbal del segmento.\n\n"
        "INSTRUCCIONES DE TRANSCRIPCIÓN MULTIMODAL:\n"
        "1. TRANSCRIPCIÓN DE AUDIO: Recupera todo el contenido dicho verbalmente por el ponente, "
        "explicaciones exactas, ejemplos y detalles técnicos. Está estrictamente prohibido resumir o simplificar.\n"
        "2. EXTRACCIÓN DE TEXTO VISUAL (OCR): Transcribe fielmente todo texto relevante que aparezca en pantalla "
        "(diapositivas, títulos, términos clave, URLs, fragmentos de código, fórmulas matemáticas o ecuaciones).\n"
        "3. DESCRIPCIÓN DE ELEMENTOS GRÁFICOS: Describe detalladamente esquemas, diagramas, diagramas de flujo, "
        "gráficos, tablas de datos o imágenes relevantes en pantalla, explicando qué conceptos o relaciones representan.\n"
        "4. CÓDIGO Y ESPECIFICACIONES: Si en pantalla aparece código fuente o comandos, recréalos íntegramente en bloques de código markdown.\n\n"
        "ESTÁ ESTRICTAMENTE PROHIBIDO RESUMIR O SIMPLIFICAR; mantén la secuencia cronológica y detalla cada elemento visual clave para que el material resultante sirva de fuente fáctica 100% fiel."
    )

    # Prompt de transcripción fiel para VIDEO (multimodal: audio + visual)
    FAITHFUL_VIDEO_PROMPT = (
        "Transcribe fielmente todo el contenido de este segmento de video. "
        "Incluye:\n"
        "- Todo lo que se dice verbalmente (transcripción literal del audio, sin resumir).\n"
        "- Todo texto visible en pantalla (diapositivas, código fuente, títulos, subtítulos, anotaciones, URLs).\n"
        "- Descripción breve de esquemas, diagramas o gráficos relevantes que aparezcan.\n"
        "- Fórmulas matemáticas o ecuaciones visibles.\n\n"
        "REGLAS ESTRICTAS:\n"
        "- NO resumas ni simplifiques bajo ninguna circunstancia.\n"
        "- NO añadas opiniones, observaciones ni interpretaciones.\n"
        "- Mantén el orden cronológico del contenido.\n"
        "- Usa formato Markdown limpio para estructurar.\n"
        "- Si se dictan fragmentos de código, transcríbelos ÍNTEGRAMENTE.\n"
        "- Escribe en español con la mejor ortografía posible."
    )

    # Prompt de transcripción fiel para AUDIO (solo contenido hablado)
    FAITHFUL_AUDIO_PROMPT = (
        "Transcribe fielmente todo el contenido hablado en este segmento de audio. "
        "Incluye:\n"
        "- Cada palabra dicha por el(los) ponente(s), sin resumir ni parafrasear.\n"
        "- Si se mencionan términos técnicos, acrónimos o siglas, transcríbelos tal cual.\n"
        "- Si se dictan fragmentos de código o especificaciones técnicas, transcríbelos ÍNTEGRAMENTE.\n\n"
        "REGLAS ESTRICTAS:\n"
        "- NO resumas ni simplifiques bajo ninguna circunstancia.\n"
        "- NO añadas opiniones, observaciones ni interpretaciones.\n"
        "- Mantén el orden cronológico del contenido.\n"
        "- Escribe en español con la mejor ortografía posible."
    )

    def generate_faithful_source_transcription(
        self,
        media_path: str,
        segment_duration_min: float = 5.0,
        language: str = "es",
        on_progress: Optional[Callable[[str], None]] = None,
        session_dir: Optional[str] = None
    ) -> str:
        """
        Genera una transcripción fiel y completa del video/audio completo,
        incluyendo contenido visual (para video) y hablado.
        
        Esta transcripción se usa como "Fuente de Consulta" para contextualizar
        la generación de flashcards en segmentos individuales.
        
        Args:
            media_path: Ruta al archivo de video o audio.
            segment_duration_min: Duración de cada segmento de transcripción en minutos.
            language: Código de idioma.
            on_progress: Callback para reportar progreso.
            session_dir: Directorio de sesión para guardar archivos temporales.
            
        Returns:
            Texto completo de la transcripción fiel concatenada.
        """
        log = on_progress or self._log
        
        is_audio_file = media_path.lower().endswith(
            ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus')
        )
        media_label = "AUDIO" if is_audio_file else "VIDEO"
        
        log(f"\n{'='*60}")
        log(f"📋 GENERANDO FUENTE DE CONSULTA ({media_label})")
        log(f"{'='*60}")
        
        # 1. Obtener duración total
        duration = self._get_video_duration(media_path)
        if duration is None or duration <= 0:
            log("❌ No se pudo obtener la duración del archivo")
            return ""
        
        segment_duration_sec = segment_duration_min * 60
        log(f"   ⏱ Duración total: {duration/60:.1f} min")
        log(f"   ✂️ Segmento de fuente: {segment_duration_min} min")
        
        # 2. Crear segmentos SIN overlap (para fuente, queremos cobertura completa sin duplicados)
        source_segments = self.segment_by_fixed_duration(
            video_duration=duration,
            segment_duration=segment_duration_sec,
            overlap=0  # Sin overlap para fuente
        )
        
        log(f"   📊 Segmentos de fuente a transcribir: {len(source_segments)}")
        
        # 3. Crear directorio temporal para chunks de fuente
        if not session_dir:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir = os.path.join(self.TEMP_DIR, f"source_{session_id}")
        
        source_chunks_dir = os.path.join(session_dir, "source_chunks")
        os.makedirs(source_chunks_dir, exist_ok=True)
        
        # 4. Extraer segmentos de media
        log(f"\n✂️ Extrayendo {len(source_segments)} segmentos de {media_label.lower()}...")
        for i, seg in enumerate(source_segments, 1):
            log(f"   [{i}/{len(source_segments)}] {seg.get_time_range_str()}")
            self.extract_video_segment(media_path, seg, source_chunks_dir)
        
        # 5. Subir todos los segmentos a Gemini
        log(f"\n⬆️ Subiendo {len(source_segments)} segmentos a Gemini...")
        client = self._get_gemini_client()
        uploaded_files = {}
        
        for i, seg in enumerate(source_segments, 1):
            if seg.audio_path and os.path.exists(seg.audio_path):
                log(f"   [{i}/{len(source_segments)}] Subiendo segmento {seg.segment_id}...")
                try:
                    myfile = self._upload_file_with_retry(client, seg.audio_path)
                    uploaded_files[seg.segment_id] = myfile
                except Exception as e:
                    log(f"   ❌ Error subiendo segmento {seg.segment_id}: {e}")
        
        # 6. Esperar procesamiento
        log(f"\n⏳ Esperando procesamiento en Gemini...")
        for seg_id, myfile in uploaded_files.items():
            while myfile.state.name == "PROCESSING":
                time.sleep(3)
                myfile = client.files.get(name=myfile.name)
                uploaded_files[seg_id] = myfile
            
            if myfile.state.name == "FAILED":
                log(f"   ❌ Falla en servidor para segmento {seg_id}")
            else:
                log(f"   ✅ Segmento {seg_id} listo")
        
        # 7. Transcribir fielmente cada segmento
        prompt = self.FAITHFUL_AUDIO_PROMPT if is_audio_file else self.FAITHFUL_VIDEO_PROMPT
        
        log(f"\n📝 Transcribiendo fielmente {len(source_segments)} segmentos...")
        transcription_parts = []
        
        for i, seg in enumerate(source_segments, 1):
            myfile = uploaded_files.get(seg.segment_id)
            if not myfile or myfile.state.name == "FAILED":
                log(f"   ⚠️ Saltando segmento {seg.segment_id} (no disponible)")
                continue
            
            log(f"   [{i}/{len(source_segments)}] Transcribiendo segmento {seg.segment_id} ({seg.get_time_range_str()})...")
            
            try:
                text = self._generate_with_fallback(myfile, prompt)
                if text and text.strip():
                    transcription_parts.append(
                        f"--- Segmento {seg.segment_id} ({seg.get_time_range_str()}) ---\n{text.strip()}"
                    )
                    log(f"      ✅ {len(text)} caracteres transcritos")
                else:
                    log(f"      ⚠️ Transcripción vacía para segmento {seg.segment_id}")
            except Exception as e:
                log(f"      ❌ Error transcribiendo segmento {seg.segment_id}: {e}")
            
            # Cooldown entre segmentos
            if i < len(source_segments):
                log(f"   ⏳ Cooldown de 10s...")
                time.sleep(10)
        
        # 8. Limpiar archivos de la API
        log(f"\n🧹 Limpiando archivos temporales de Gemini...")
        for seg_id, myfile in uploaded_files.items():
            try:
                client.files.delete(name=myfile.name)
            except Exception:
                pass
        
        # 9. Concatenar todo
        full_transcription = "\n\n".join(transcription_parts)
        
        if not full_transcription.strip():
            log("❌ No se pudo generar la transcripción de fuente")
            return ""
        
        # 10. Guardar archivo de fuente
        source_file_path = os.path.join(session_dir, "transcripcion_fuente_completa.md")
        try:
            with open(source_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Transcripción Fiel Completa ({media_label})\n")
                f.write(f"# Archivo: {os.path.basename(media_path)}\n")
                f.write(f"# Duración: {duration/60:.1f} min\n")
                f.write(f"# Segmentos: {len(transcription_parts)}\n\n")
                f.write(full_transcription)
            log(f"   💾 Fuente guardada: {source_file_path}")
        except Exception as e:
            log(f"   ⚠️ Error guardando fuente: {e}")
        
        # Limpiar chunks temporales de fuente (el archivo final ya está guardado)
        try:
            shutil.rmtree(source_chunks_dir, ignore_errors=True)
        except Exception:
            pass
        
        log(f"\n✅ FUENTE DE CONSULTA GENERADA: {len(full_transcription):,} caracteres")
        log(f"{'='*60}\n")
        
        return full_transcription

