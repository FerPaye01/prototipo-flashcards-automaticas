"""
Gestor de Recursos de Modelos de IA (ModelResourceManager).
Implementa el Patrón Singleton para controlar estrictamente la VRAM y evitar desbordamientos
al cargar múltiples modelos pesados (Florence-2, Marker, Whisper, etc.) en entornos multihilo.
"""

import threading
import gc
import logging
from typing import Dict, Any, Optional

# Configuramos logger simple para este módulo
logger = logging.getLogger("VRAM_Manager")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class ModelResourceManager:
    """
    Gestor Singleton para el control de la memoria VRAM.
    Asegura que las cargas y descargas de modelos sean thread-safe.
    """
    _instance = None
    _lock = threading.Lock()  # Lock para garantizar Singleton en multihilo

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelResourceManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        """Inicializa el estado interno del gestor."""
        self.loaded_models: Dict[str, Any] = {}
        # Lock de operaciones: evita que dos hilos intenten cargar modelos pesados a la vez
        self.resource_lock = threading.RLock() 
        logger.info("ModelResourceManager inicializado.")

    def register_model(self, model_name: str, model_instance: Any):
        """
        Registra un modelo cargado en la memoria.
        """
        with self.resource_lock:
            self.loaded_models[model_name] = model_instance
            logger.info(f"Modelo registrado en memoria: {model_name}")

    def get_model(self, model_name: str) -> Optional[Any]:
        """Obtiene una referencia al modelo si está cargado."""
        with self.resource_lock:
            return self.loaded_models.get(model_name)

    def is_loaded(self, model_name: str) -> bool:
        """Verifica si un modelo ya está en VRAM."""
        with self.resource_lock:
            return model_name in self.loaded_models

    def unload_model(self, model_name: str):
        """
        Descarga un modelo específico de la memoria y fuerza la liberación de VRAM.
        """
        with self.resource_lock:
            if model_name in self.loaded_models:
                logger.info(f"Descargando modelo: {model_name}...")
                
                # Eliminar la referencia explícitamente
                del self.loaded_models[model_name]
                
                # Forzar recolección de basura
                self.force_garbage_collection()
                logger.info(f"Modelo {model_name} descargado exitosamente.")
            else:
                logger.debug(f"Intento de descargar {model_name}, pero no estaba en memoria.")

    def unload_all_except(self, keep_models: list):
        """
        Descarga todos los modelos excepto los especificados en la lista.
        Útil para hacer espacio antes de cargar un modelo muy grande.
        """
        with self.resource_lock:
            models_to_remove = [name for name in self.loaded_models.keys() if name not in keep_models]
            if not models_to_remove:
                return
                
            logger.info(f"Limpiando espacio. Descargando: {models_to_remove}")
            for name in models_to_remove:
                del self.loaded_models[name]
                
            self.force_garbage_collection()

    def unload_all(self):
        """Descarga TODOS los modelos cargados."""
        with self.resource_lock:
            if not self.loaded_models:
                return
                
            logger.info("Descargando TODOS los modelos pesados de la VRAM...")
            self.loaded_models.clear()
            self.force_garbage_collection()
            logger.info("Memoria VRAM completamente limpiada.")

    def force_garbage_collection(self):
        """
        Invoca al recolector de basura de Python y a CUDA para liberar la memoria 
        no referenciada inmediatamente.
        """
        # 1. Recolección nativa de Python
        gc.collect()
        
        # 2. Vaciado de caché de PyTorch si está disponible
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            logger.info("CUDA Cache vaciada (torch.cuda.empty_cache).")
