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

# playsound para reproducción
try:
    from playsound import playsound
    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False


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
    SUPPORTED_FORMATS = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.mov')
    
    # Directorio temporal
    TEMP_DIR = os.path.join("Flashcards Programa", "temp_videos")
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """Inicializa el procesador."""
        self.log_callback = log_callback or print
        self._ensure_temp_dir()
        
        # Cargar API Keys de Gemini
        self.api_keys = []
        keys_str = os.environ.get("GEMINI_API_KEYS_OCR", "")
        if keys_str:
            self.api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            
        self.current_key_index = 0
    
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
        
        # Verificar tamaño
        size = os.path.getsize(video_path)
        size_mb = size / (1024 * 1024)
        if size > self.MAX_SIZE:
            return False, f"Archivo muy grande ({size_mb:.1f} MB). Máximo: {self.MAX_SIZE / (1024*1024*1024):.0f}GB"
        
        # Obtener duración real del video
        duration = self._get_video_duration(video_path)
        
        if duration is None:
            # Si no podemos obtener la duración, asumir que es válido
            self._log("⚠️ No se pudo obtener duración del video, procesando de todos modos")
            return True, f"Video válido (tamaño: {size_mb:.1f} MB)"
        
        duration_min = duration / 60
        
        if duration > self.MAX_DURATION:
            return False, f"Video muy largo ({duration_min:.1f} min). Máximo: {self.MAX_DURATION / 3600:.0f} horas"
        
        return True, f"Video válido ({duration_min:.1f} min, {size_mb:.1f} MB)"
    
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
        """Genera contenido usando fallback de modelos con reintentos por rate limit.
        
        IMPORTANTE: Los archivos subidos a Gemini están vinculados a la API Key
        que los subió. NO se puede rotar a otra key para acceder al mismo archivo.
        En su lugar, se espera y reintenta con la misma key.
        """
        models = [os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"), "gemini-2.5-flash"]
        max_retries = 3  # Reintentos por rate limit por modelo
        
        for model_name in models:
            self._log(f"   🤖 Intentando con modelo {model_name}...")
            
            for attempt in range(max_retries):
                client = self._get_gemini_client()
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[file_obj, prompt]
                    )
                    return response.text
                except Exception as e:
                    error_str = str(e).lower()
                    
                    if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                        wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s
                        remaining = max_retries - attempt - 1
                        if remaining > 0:
                            self._log(f"   ⏳ Rate limit alcanzado. Esperando {wait_time}s antes de reintentar ({remaining} intentos restantes)...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self._log(f"   ❌ Rate limit persistente para {model_name} tras {max_retries} intentos.")
                            break  # Probar el siguiente modelo
                    elif "permission_denied" in error_str or "403" in error_str:
                        self._log(f"   ❌ Permiso denegado para {model_name} (archivo no accesible con esta key): {e}")
                        break  # No tiene sentido reintentar, probar siguiente modelo
                    else:
                        self._log(f"   ❌ Error de Gemini ({model_name}): {e}")
                        break  # Si es otro error, probar el siguiente modelo
        
        raise Exception("Todos los modelos y API keys fallaron.")
    
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
        Extrae un chunk de video (MP4) usando copia directa de streams.
        
        Args:
            video_path: Ruta al video original
            segment: VideoSegment a extraer
            output_dir: Directorio de salida
            
        Returns:
            Ruta al archivo de video MP4 extraído
        """
        output_path = os.path.join(
            output_dir,
            f"segment_{segment.segment_id:03d}.mp4"
        )
        
        try:
            # Calcular tiempo de inicio en formato HH:MM:SS
            start_time = str(int(segment.start_time // 3600)).zfill(2) + ":" + \
                        str(int((segment.start_time % 3600) // 60)).zfill(2) + ":" + \
                        str(int(segment.start_time % 60)).zfill(2)
            
            # Construir y ejecutar el comando ffmpeg directamente con '-c copy'
            cmd = [
                'ffmpeg',
                '-y',  # Sobrescribir
                '-i', video_path,
                '-ss', start_time,
                '-t', str(segment.duration),
                '-c', 'copy',
                output_path
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                self._log(f"❌ Error de ffmpeg: {result.stderr.decode('utf-8', errors='ignore')[-200:]}")
                return None
            
            if os.path.exists(output_path):
                segment.audio_path = output_path # Mantener la propiedad para compatibilidad
                return output_path
            else:
                self._log(f"❌ No se pudo extraer video del segmento {segment.segment_id}")
                return None
        
        except Exception as e:
            self._log(f"❌ Error extrayendo video del segmento {segment.segment_id}: {e}")
            return None
    
    def transcribe_video_segment(
        self,
        segment: VideoSegment,
        language: str = "es",
        pre_uploaded_file=None,
        skip_cleanup: bool = False
    ) -> str:
        """
        Transcribe un segmento de video completo usando Gemini Multimodal.
        
        Args:
            segment: VideoSegment con audio_path (ahora es un MP4)
            language: Código de idioma (Omitido para Gemini, que detecta automático)
            pre_uploaded_file: Objeto de archivo de Gemini si ya se subió y procesó previamente
            skip_cleanup: Si es True, no elimina el archivo de la API después de transcribir
            
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
                
            prompt = (
                "Actúa como un excelente estudiante universitario especializado, elaborando "
                "material de estudio integral basado en el contenido audiovisual proporcionado. "
                "Recibes la imagen del video de manera sincronizada con la voz. "
                "Tu instrucción ESTRICTA es integrar y consolidar paso a paso todo el conocimiento visual "
                "(diapositivas, esquemas, ejemplos en pantalla) que aparezca a lo largo del tiempo, "
                "en conjunto cronológico con las explicaciones verbales exactas del ponente. "
                "Debes añadir observaciones y apuntes complementarios como estudiante resaltando "
                "lo relevante del contenido, todo con la mejor ortografía y puntuación posibles en español. "
                "ESTÁ ESTRICTAMENTE PROHIBIDO SIMPLIFICAR O RESUMIR; no debes perder información sin importar "
                "qué tan largo sea. Debes recuperar hasta el último detalle técnico válido mostrado o dicho. "
                "ADICIONALMENTE: Si detectas fragmentos de CÓDIGO o ESPECIFICACIONES TÉCNICAS, debes recrearlos "
                "ÍNTEGRAMENTE sin modificar ni una sola línea de sintaxis. Si es una REUNIÓN, identifica participantes y acuerdos."
            )
            
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
        father_prefix: str = ""
    ) -> Dict[str, Any]:
        """
        Procesa un video completo: valida, segmenta, extrae audio y transcribe.
        
        Args:
            video_path: Ruta al video
            segment_duration: Duración objetivo de segmentos en segundos
            overlap: Overlap entre segmentos en segundos
            use_silence_detection: Usar detección de silencios
            use_transcription_analysis: Usar análisis de transcripción
            language: Idioma del video
            
        Returns:
            Dict con información del procesamiento
        """
        self._log("\n" + "="*60)
        self._log("🎬 PROCESANDO VIDEO")
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
        
        # 4. Determinar puntos de corte (segmentación fija por ahora)
        self._log(f"\n✂️ Segmentando video...")
        self._log(f"   Duración del segmento: {segment_duration}s")
        self._log(f"   Overlap: {overlap}s")
        
        segments = self.segment_by_fixed_duration(
            video_duration, segment_duration, overlap
        )
        
        self._log(f"   Total de segmentos: {len(segments)}")
        
        # 5. Extraer trozos de video de cada segmento
        self._log(f"\n🎥 Extrayendo cortes de video (MP4)...")
        
        for i, segment in enumerate(segments, 1):
            self._log(f"   [{i}/{len(segments)}] Segmento {segment.segment_id}: {segment.get_time_range_str()}")
            self.extract_video_segment(video_path, segment, video_chunks_dir)
            
            # Log de tamaño según los requisitos en la interfaz
            if segment.audio_path and os.path.exists(segment.audio_path):
                size_mb = os.path.getsize(segment.audio_path) / (1024 * 1024)
                self._log(f"      📦 Tamaño: {size_mb:.2f} MB - Duración: {segment.duration}s")
        
        # 6. Fase 1: Subir todos los segmentos
        self._log(f"\n⬆️ [Fase 1] Subiendo {len(segments)} recortes de video a Gemini...")
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
        self._log(f"\n⏳ [Fase 2] Esperando que Google procese los videos (Estado ACTIVE)...")
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
    
    def play_audio(self, audio_path: str):
        """
        Reproduce un archivo de audio.
        
        Args:
            audio_path: Ruta al archivo de audio
        """
        if not PLAYSOUND_AVAILABLE:
            self._log("⚠️ playsound no está instalado. Ejecuta: pip install playsound")
            return
        
        if not os.path.exists(audio_path):
            self._log(f"❌ Archivo de audio no encontrado: {audio_path}")
            return
        
        try:
            self._log(f"▶️ Reproduciendo: {os.path.basename(audio_path)}")
            playsound(audio_path)
            self._log(f"⏹️ Reproducción finalizada")
        except Exception as e:
            self._log(f"❌ Error reproduciendo audio: {e}")
    
    def cleanup_session(self, session_dir: str):
        """Elimina los archivos temporales de una sesión."""
        try:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                self._log(f"🗑️ Sesión limpiada: {os.path.basename(session_dir)}")
        except Exception as e:
            self._log(f"⚠️ Error limpiando sesión: {e}")
