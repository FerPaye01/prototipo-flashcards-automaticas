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

# Whisper para transcripción
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# FFmpeg para procesamiento de video
try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False


class VideoSegment:
    """Representa un segmento de video."""
    
    def __init__(self, start_time: float, end_time: float, segment_id: int):
        self.start_time = start_time  # En segundos
        self.end_time = end_time
        self.segment_id = segment_id
        self.duration = end_time - start_time
        self.file_path = None
        self.transcription = ""
    
    def __repr__(self):
        return f"Segment {self.segment_id}: {self.start_time:.1f}s - {self.end_time:.1f}s ({self.duration:.1f}s)"


class VideoProcessor:
    """Procesador de videos con segmentación inteligente."""
    
    # Límites
    MAX_DURATION = 7200  # 2 horas en segundos
    MAX_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    SUPPORTED_FORMATS = ('.mp4', '.avi', '.mov', '.mkv')
    
    # Directorio temporal
    TEMP_DIR = "temp_videos"
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """Inicializa el procesador."""
        self.log_callback = log_callback or print
        self.whisper_model = None
        self._ensure_temp_dir()
    
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
        if size > self.MAX_SIZE:
            size_mb = size / (1024 * 1024)
            return False, f"Archivo muy grande ({size_mb:.1f} MB). Máximo: 2GB"
        
        # Verificar duración con ffprobe
        try:
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
            
            if duration > self.MAX_DURATION:
                duration_min = duration / 60
                return False, f"Video muy largo ({duration_min:.1f} min). Máximo: 2 horas"
            
            return True, f"Video válido ({duration/60:.1f} min, {size/(1024*1024):.1f} MB)"
        
        except Exception as e:
            return False, f"Error al leer video: {e}"
    
    def load_whisper_model(self, model_size: str = "base"):
        """
        Carga el modelo de Whisper.
        
        Args:
            model_size: tiny, base, small, medium, large
        """
        if not WHISPER_AVAILABLE:
            raise ImportError("Whisper no está instalado. Ejecuta: pip install openai-whisper")
        
        if self.whisper_model is None:
            self._log(f"🔄 Cargando modelo Whisper '{model_size}'...")
            self.whisper_model = whisper.load_model(model_size)
            self._log(f"✅ Modelo Whisper cargado")
    
    def transcribe_video(self, video_path: str, language: str = "es") -> Dict[str, Any]:
        """
        Transcribe el audio del video usando Whisper.
        
        Args:
            video_path: Ruta al video
            language: Código de idioma (es, en, etc.)
            
        Returns:
            Dict con transcripción y timestamps
        """
        self.load_whisper_model()
        
        self._log("🎤 Transcribiendo audio con Whisper...")
        
        try:
            result = self.whisper_model.transcribe(
                video_path,
                language=language,
                word_timestamps=True,
                verbose=False
            )
            
            self._log(f"✅ Transcripción completada: {len(result['text'])} caracteres")
            
            return result
        
        except Exception as e:
            self._log(f"❌ Error en transcripción: {e}")
            return None
    
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
    
    def cut_video_segment(
        self,
        video_path: str,
        segment: VideoSegment,
        output_dir: str
    ) -> str:
        """
        Corta un segmento del video.
        
        Args:
            video_path: Ruta al video original
            segment: VideoSegment a extraer
            output_dir: Directorio de salida
            
        Returns:
            Ruta al archivo del segmento
        """
        output_path = os.path.join(
            output_dir,
            f"segment_{segment.segment_id:03d}.mp4"
        )
        
        try:
            # Usar ffmpeg para cortar
            (
                ffmpeg
                .input(video_path, ss=segment.start_time, t=segment.duration)
                .output(output_path, codec='copy', loglevel='error')
                .overwrite_output()
                .run()
            )
            
            segment.file_path = output_path
            return output_path
        
        except Exception as e:
            self._log(f"❌ Error cortando segmento {segment.segment_id}: {e}")
            return None
    
    def process_video(
        self,
        video_path: str,
        segment_duration: float = 180,
        overlap: float = 30,
        use_silence_detection: bool = False,
        use_transcription_analysis: bool = True,
        language: str = "es"
    ) -> Dict[str, Any]:
        """
        Procesa un video completo: valida, transcribe y segmenta.
        
        Args:
            video_path: Ruta al video
            segment_duration: Duración objetivo de segmentos
            overlap: Overlap entre segmentos
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
        probe = ffmpeg.probe(video_path)
        video_duration = float(probe['format']['duration'])
        
        # 3. Crear sesión temporal
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(self.TEMP_DIR, f"session_{session_id}")
        segments_dir = os.path.join(session_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)
        
        # 4. Transcribir (si se requiere análisis)
        transcription = None
        if use_transcription_analysis:
            transcription = self.transcribe_video(video_path, language)
            
            if transcription:
                # Guardar transcripción
                trans_path = os.path.join(session_dir, "transcription.json")
                with open(trans_path, 'w', encoding='utf-8') as f:
                    json.dump(transcription, f, ensure_ascii=False, indent=2)
        
        # 5. Determinar puntos de corte
        fixed_cuts = []
        silence_cuts = []
        transcription_cuts = []
        
        # Cortes fijos
        segments_fixed = self.segment_by_fixed_duration(
            video_duration, segment_duration, overlap
        )
        fixed_cuts = [s.start_time for s in segments_fixed[1:]]  # Excluir el primero (0)
        
        # Cortes por silencio
        if use_silence_detection:
            silence_cuts = self.segment_by_silence(video_path)
        
        # Cortes por transcripción
        if transcription:
            transcription_cuts = self.segment_by_transcription_analysis(
                transcription, segment_duration
            )
        
        # Combinar puntos de corte
        cut_points = self.merge_cut_points(
            fixed_cuts, silence_cuts, transcription_cuts
        )
        
        # Crear segmentos finales
        segments = self.create_segments_from_cuts(cut_points, video_duration)
        
        self._log(f"\n📊 Total de segmentos: {len(segments)}")
        
        # 6. Cortar video en segmentos
        self._log("\n✂️ Cortando video en segmentos...")
        
        for i, segment in enumerate(segments, 1):
            self._log(f"   Segmento {i}/{len(segments)}: {segment.start_time:.1f}s - {segment.end_time:.1f}s")
            self.cut_video_segment(video_path, segment, segments_dir)
        
        # 7. Guardar metadata
        metadata = {
            "session_id": session_id,
            "original_video": os.path.basename(video_path),
            "duration": video_duration,
            "language": language,
            "segment_duration": segment_duration,
            "overlap": overlap,
            "use_silence_detection": use_silence_detection,
            "use_transcription_analysis": use_transcription_analysis,
            "segments": [
                {
                    "id": s.segment_id,
                    "start": s.start_time,
                    "end": s.end_time,
                    "duration": s.duration,
                    "file": os.path.basename(s.file_path) if s.file_path else None
                }
                for s in segments
            ]
        }
        
        metadata_path = os.path.join(session_dir, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        self._log("\n✅ Procesamiento completado")
        self._log("="*60 + "\n")
        
        return {
            "success": True,
            "session_dir": session_dir,
            "segments_dir": segments_dir,
            "segments": segments,
            "transcription": transcription,
            "metadata": metadata
        }
    
    def cleanup_session(self, session_dir: str):
        """Elimina los archivos temporales de una sesión."""
        try:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                self._log(f"🗑️ Sesión limpiada: {os.path.basename(session_dir)}")
        except Exception as e:
            self._log(f"⚠️ Error limpiando sesión: {e}")
