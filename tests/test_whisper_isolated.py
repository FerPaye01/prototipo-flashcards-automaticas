
import os
import sys
import warnings
import shutil
import subprocess

# Suppress warnings
warnings.filterwarnings("ignore")

def check_ffmpeg():
    """Verifica si ffmpeg está disponible y ofrece diagnóstico."""
    print("\n🔍 Verificando dependencias (ffmpeg)...")
    
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"✅ FINALMENTE ENCONTRADO: ffmpeg en '{ffmpeg_path}'")
        try:
            # Probar ejecución simple
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            print(f"   Versión detectada: {result.stdout.splitlines()[0]}")
            return True
        except Exception as e:
            print(f"⚠️ ffmpeg encontrado pero error al ejecutar: {e}")
            return False
    else:
        print("❌ ERROR CRÍTICO: 'ffmpeg' NO encontrado en el PATH.")
        print("   Whisper NECESITA ffmpeg para leer el audio, aunque audio_extract funcione.")
        print("   audio_extract usa su propio binario o imageio, pero Whisper usa el del sistema.")
        
        # Sugerencia de solución
        print("\n🛠️ SOLUCIÓN MÁS RÁPIDA:")
        print("1. Descarga ffmpeg (build 'essentials' o 'full') desde https://gyan.dev/ffmpeg/builds/")
        print("   (o busca 'ffmpeg release essentials.zip')")
        print("2. Extrae el archivo ZIP.")
        print("3. Copia 'ffmpeg.exe' (dentro de la carpeta 'bin') a:")
        print(f"   📂 {os.getcwd()}")
        print("   (Es decir, pon ffmpeg.exe junto a este script)")
        return False

def test_whisper():
    print("----------------------------------------------------------------")
    print("🧪 INICIANDO PRUEBA AISLADA DE WHISPER + AUDIO_EXTRACT")
    print("----------------------------------------------------------------")
    
    # 0. Check FFmpeg FIRST
    ffmpeg_ok = check_ffmpeg()
    
    # Si no esta en el PATH, intentar añadir el directorio actual al PATH temporalmente
    if not ffmpeg_ok:
        current_dir = os.getcwd()
        if os.path.exists(os.path.join(current_dir, "ffmpeg.exe")):
            print(f"\n⚠️ ffmpeg.exe detectado en carpeta local. Añadiendo al PATH temporal...")
            os.environ["PATH"] += os.pathsep + current_dir
            if check_ffmpeg():
                print("✅ ffmpeg local configurado correctamente para esta sesión.")
            else:
                print("❌ Aún así falló la verificación de ffmpeg local.")
                return
        else:
            print("\n❌ No se encontró ffmpeg.exe en el sistema ni en la carpeta actual.")
            print("   Por favor sigue las instrucciones de arriba para colocar ffmpeg.exe aquí.")
            return

    # 1. Check Whisper
    try:
        import whisper
        print("\n✅ Módulo 'whisper' importado correctamente.")
    except ImportError:
        print("❌ Error: No se pudo importar 'whisper'.")
        print("   Ejecuta: pip install openai-whisper")
        return

    # 2. Check audio_extract
    try:
        from audio_extract import extract_audio
        print("✅ Módulo 'audio_extract' importado correctamente.")
    except ImportError:
        print("❌ Error: No se pudo importar 'audio_extract'.")
        print("   Ejecuta: pip install audio-extract")
        return

    # 3. Load Model
    model_size = "base"
    print(f"\n🔄 Cargando modelo Whisper '{model_size}'...")
    
    # Configurar ruta de descarga en el disco actual (E:) para evitar llenar C:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(current_dir, "whisper_models")
    os.makedirs(models_dir, exist_ok=True)
    
    print(f"   📂 Directorio de modelos: {models_dir}")
    
    try:
        # Usar download_root para especificar la carpeta
        model = whisper.load_model(model_size, download_root=models_dir)
        print(f"✅ Modelo '{model_size}' cargado exitosamente.")
    except Exception as e:
        print(f"❌ Error cargando el modelo: {e}")
        return

    # 4. Extract Audio
    video_file = "test1.mp4"
    audio_file = "test_audio_extract.mp3"
    
    if not os.path.exists(video_file):
        print(f"\n❌ Error: No se encuentra el archivo de video '{video_file}' para la prueba.")
        # Crear dummy video file logic removed to keep it simple as user said wait
        print("   Por favor asegúrate de que 'test1.mp4' existe en esta carpeta.")
        return

    print(f"\n🎵 Extrayendo audio de '{video_file}' usando audio_extract...")
    
    try:
        # Using the syntax user provided/requested
        extract_audio(input_path=video_file, output_path=audio_file, overwrite=True)
        
        if os.path.exists(audio_file):
             print(f"✅ Audio extraído exitosamente: {audio_file}")
        else:
             print(f"❌ Error: El archivo de audio no se creó.")
             return
    except Exception as e:
        print(f"❌ Error durante la extracción de audio: {e}")
        return

    # 5. Transcribe
    try:
        print("\n🎤 Transcribiendo audio extraído...")
        # Verify if whisper can read it (this step explicitly uses ffmpeg via subprocess)
        result = model.transcribe(audio_file)
        
        text = result['text'].strip()
        print("✅ Transcripción completada.")
        print(f"   Texto detectado (primeros 100 chars): '{text[:100]}...'")
        
    except Exception as e:
        print(f"❌ Error en la transcripción: {e}")
        print("   Causa: Whisper falló al invocar ffmpeg.")
    finally:
        # Cleanup
        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
                print("🧹 Archivo de audio temporal eliminado.")
            except:
                pass
            
    print("\n----------------------------------------------------------------")
    print("🎉 PRUEBA FINALIZADA")
    print("----------------------------------------------------------------")

if __name__ == "__main__":
    test_whisper()
