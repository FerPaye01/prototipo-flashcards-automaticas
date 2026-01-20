"""
Configuration and Settings Management System

This module provides centralized configuration management for the flashcard
automation system, including user preferences, processing options, and
application settings with persistence and validation.
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum
import threading
from datetime import datetime

from input_method_controller import InputMode


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""
    pass


class ValidationLevel(Enum):
    """Validation levels for configuration values."""
    STRICT = "strict"
    LENIENT = "lenient"
    DISABLED = "disabled"


@dataclass
class UserPreferences:
    """User preference settings."""
    default_input_method: str = "pdf_annotations"
    remember_last_input_method: bool = True
    last_used_input_method: Optional[str] = None
    auto_clear_chat_after_processing: bool = True
    show_processing_progress: bool = True
    confirm_before_processing: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserPreferences':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class PDFProcessingOptions:
    """PDF processing configuration options."""
    default_annotation_mode: str = "con"  # "con" or "sin"
    extract_headers_footers: bool = False
    preserve_formatting: bool = True
    handle_multi_column: bool = True
    filter_page_numbers: bool = True
    min_annotation_length: int = 10
    max_file_size_mb: int = 50
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PDFProcessingOptions':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class TextValidationSettings:
    """Text validation configuration settings."""
    min_text_length: int = 10
    max_text_length: int = 50000
    min_unique_characters: int = 5
    require_alphabetic_content: bool = True
    max_repetition_ratio: float = 0.8
    validation_level: str = "lenient"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextValidationSettings':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class ProcessingSettings:
    """Processing pipeline configuration settings."""
    api_delay_seconds: int = 60
    max_retries: int = 3
    timeout_seconds: int = 300
    enable_debug_logging: bool = False
    auto_import_to_anki: bool = True
    backup_flashcards: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingSettings':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class ApplicationConfig:
    """Complete application configuration."""
    user_preferences: UserPreferences = field(default_factory=UserPreferences)
    pdf_processing: PDFProcessingOptions = field(default_factory=PDFProcessingOptions)
    text_validation: TextValidationSettings = field(default_factory=TextValidationSettings)
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)
    version: str = "1.0.0"
    last_updated: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_preferences": self.user_preferences.to_dict(),
            "pdf_processing": self.pdf_processing.to_dict(),
            "text_validation": self.text_validation.to_dict(),
            "processing": self.processing.to_dict(),
            "version": self.version,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApplicationConfig':
        """Create from dictionary."""
        return cls(
            user_preferences=UserPreferences.from_dict(data.get("user_preferences", {})),
            pdf_processing=PDFProcessingOptions.from_dict(data.get("pdf_processing", {})),
            text_validation=TextValidationSettings.from_dict(data.get("text_validation", {})),
            processing=ProcessingSettings.from_dict(data.get("processing", {})),
            version=data.get("version", "1.0.0"),
            last_updated=data.get("last_updated")
        )


class ConfigurationManager:
    """
    Centralized configuration management system with persistence,
    validation, and thread-safe access.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file (default: flashcards_config.json)
        """
        self.logger = logging.getLogger(__name__)
        
        # Configuration file path
        if config_file is None:
            config_file = "flashcards_config.json"
        self.config_file = Path(config_file)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Configuration data
        self._config: ApplicationConfig = ApplicationConfig()
        self._is_loaded = False
        self._change_callbacks: List[callable] = []
        
        # Load configuration
        self.load_configuration()
    
    def load_configuration(self) -> bool:
        """
        Load configuration from file.
        
        Returns:
            True if loaded successfully, False if using defaults
        """
        with self._lock:
            try:
                if self.config_file.exists():
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    self._config = ApplicationConfig.from_dict(data)
                    self._is_loaded = True
                    self.logger.info(f"Configuration loaded from {self.config_file}")
                    return True
                
                else:
                    # Create default configuration
                    self._config = ApplicationConfig()
                    self._config.last_updated = datetime.now().isoformat()
                    self.save_configuration()
                    self.logger.info("Created default configuration")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Error loading configuration: {e}")
                self._config = ApplicationConfig()
                self._is_loaded = False
                return False
    
    def save_configuration(self) -> bool:
        """
        Save configuration to file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        with self._lock:
            try:
                # Update timestamp
                self._config.last_updated = datetime.now().isoformat()
                
                # Create directory if needed
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Save to file
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Configuration saved to {self.config_file}")
                
                # Notify callbacks
                self._notify_change_callbacks()
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error saving configuration: {e}")
                return False
    
    def get_config(self) -> ApplicationConfig:
        """
        Get complete configuration.
        
        Returns:
            ApplicationConfig instance
        """
        with self._lock:
            return self._config
    
    def get_user_preferences(self) -> UserPreferences:
        """Get user preferences."""
        with self._lock:
            return self._config.user_preferences
    
    def get_pdf_processing_options(self) -> PDFProcessingOptions:
        """Get PDF processing options."""
        with self._lock:
            return self._config.pdf_processing
    
    def get_text_validation_settings(self) -> TextValidationSettings:
        """Get text validation settings."""
        with self._lock:
            return self._config.text_validation
    
    def get_processing_settings(self) -> ProcessingSettings:
        """Get processing settings."""
        with self._lock:
            return self._config.processing
    
    def update_user_preferences(self, **kwargs) -> bool:
        """
        Update user preferences.
        
        Args:
            **kwargs: Preference values to update
            
        Returns:
            True if updated successfully
        """
        with self._lock:
            try:
                for key, value in kwargs.items():
                    if hasattr(self._config.user_preferences, key):
                        setattr(self._config.user_preferences, key, value)
                    else:
                        raise ValueError(f"Unknown preference: {key}")
                
                return self.save_configuration()
                
            except Exception as e:
                self.logger.error(f"Error updating user preferences: {e}")
                return False
    
    def update_pdf_processing_options(self, **kwargs) -> bool:
        """
        Update PDF processing options.
        
        Args:
            **kwargs: Option values to update
            
        Returns:
            True if updated successfully
        """
        with self._lock:
            try:
                for key, value in kwargs.items():
                    if hasattr(self._config.pdf_processing, key):
                        setattr(self._config.pdf_processing, key, value)
                    else:
                        raise ValueError(f"Unknown PDF processing option: {key}")
                
                return self.save_configuration()
                
            except Exception as e:
                self.logger.error(f"Error updating PDF processing options: {e}")
                return False
    
    def update_text_validation_settings(self, **kwargs) -> bool:
        """
        Update text validation settings.
        
        Args:
            **kwargs: Setting values to update
            
        Returns:
            True if updated successfully
        """
        with self._lock:
            try:
                for key, value in kwargs.items():
                    if hasattr(self._config.text_validation, key):
                        setattr(self._config.text_validation, key, value)
                    else:
                        raise ValueError(f"Unknown text validation setting: {key}")
                
                return self.save_configuration()
                
            except Exception as e:
                self.logger.error(f"Error updating text validation settings: {e}")
                return False
    
    def update_processing_settings(self, **kwargs) -> bool:
        """
        Update processing settings.
        
        Args:
            **kwargs: Setting values to update
            
        Returns:
            True if updated successfully
        """
        with self._lock:
            try:
                for key, value in kwargs.items():
                    if hasattr(self._config.processing, key):
                        setattr(self._config.processing, key, value)
                    else:
                        raise ValueError(f"Unknown processing setting: {key}")
                
                return self.save_configuration()
                
            except Exception as e:
                self.logger.error(f"Error updating processing settings: {e}")
                return False
    
    def get_default_input_method(self) -> InputMode:
        """
        Get the default input method as InputMode enum.
        
        Returns:
            InputMode enum value
        """
        with self._lock:
            prefs = self._config.user_preferences
            
            # Use last used method if remember is enabled
            if prefs.remember_last_input_method and prefs.last_used_input_method:
                method_str = prefs.last_used_input_method
            else:
                method_str = prefs.default_input_method
            
            # Convert string to InputMode
            try:
                if method_str == "pdf_annotations":
                    return InputMode.PDF_ANNOTATIONS
                elif method_str == "pdf_fulltext":
                    return InputMode.PDF_FULLTEXT
                elif method_str == "direct_text":
                    return InputMode.DIRECT_TEXT
                else:
                    self.logger.warning(f"Unknown input method: {method_str}, using default")
                    return InputMode.PDF_ANNOTATIONS
            except Exception as e:
                self.logger.error(f"Error converting input method: {e}")
                return InputMode.PDF_ANNOTATIONS
    
    def set_last_used_input_method(self, input_mode: InputMode) -> bool:
        """
        Set the last used input method.
        
        Args:
            input_mode: InputMode that was last used
            
        Returns:
            True if updated successfully
        """
        # Convert InputMode to string
        mode_str = input_mode.value
        
        return self.update_user_preferences(last_used_input_method=mode_str)
    
    def validate_configuration(self) -> List[str]:
        """
        Validate current configuration and return list of issues.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        issues = []
        
        with self._lock:
            config = self._config
            
            # Validate user preferences
            prefs = config.user_preferences
            valid_input_methods = ["pdf_annotations", "pdf_fulltext", "direct_text"]
            
            if prefs.default_input_method not in valid_input_methods:
                issues.append(f"Invalid default input method: {prefs.default_input_method}")
            
            if prefs.last_used_input_method and prefs.last_used_input_method not in valid_input_methods:
                issues.append(f"Invalid last used input method: {prefs.last_used_input_method}")
            
            # Validate PDF processing options
            pdf_opts = config.pdf_processing
            if pdf_opts.default_annotation_mode not in ["con", "sin"]:
                issues.append(f"Invalid annotation mode: {pdf_opts.default_annotation_mode}")
            
            if pdf_opts.min_annotation_length < 1:
                issues.append("Minimum annotation length must be at least 1")
            
            if pdf_opts.max_file_size_mb < 1:
                issues.append("Maximum file size must be at least 1 MB")
            
            # Validate text validation settings
            text_val = config.text_validation
            if text_val.min_text_length < 1:
                issues.append("Minimum text length must be at least 1")
            
            if text_val.max_text_length < text_val.min_text_length:
                issues.append("Maximum text length must be greater than minimum")
            
            if text_val.min_unique_characters < 1:
                issues.append("Minimum unique characters must be at least 1")
            
            if not (0.0 <= text_val.max_repetition_ratio <= 1.0):
                issues.append("Max repetition ratio must be between 0.0 and 1.0")
            
            if text_val.validation_level not in [v.value for v in ValidationLevel]:
                issues.append(f"Invalid validation level: {text_val.validation_level}")
            
            # Validate processing settings
            proc_set = config.processing
            if proc_set.api_delay_seconds < 0:
                issues.append("API delay must be non-negative")
            
            if proc_set.max_retries < 0:
                issues.append("Max retries must be non-negative")
            
            if proc_set.timeout_seconds < 1:
                issues.append("Timeout must be at least 1 second")
        
        return issues
    
    def reset_to_defaults(self) -> bool:
        """
        Reset configuration to default values.
        
        Returns:
            True if reset successfully
        """
        with self._lock:
            try:
                self._config = ApplicationConfig()
                self._config.last_updated = datetime.now().isoformat()
                
                success = self.save_configuration()
                if success:
                    self.logger.info("Configuration reset to defaults")
                
                return success
                
            except Exception as e:
                self.logger.error(f"Error resetting configuration: {e}")
                return False
    
    def register_change_callback(self, callback: callable):
        """
        Register a callback to be called when configuration changes.
        
        Args:
            callback: Function to call when configuration changes
        """
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)
    
    def unregister_change_callback(self, callback: callable):
        """
        Unregister a change callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def _notify_change_callbacks(self):
        """Notify all registered callbacks of configuration changes."""
        for callback in self._change_callbacks:
            try:
                callback(self._config)
            except Exception as e:
                self.logger.error(f"Error in configuration change callback: {e}")
    
    def export_configuration(self, file_path: str) -> bool:
        """
        Export configuration to a file.
        
        Args:
            file_path: Path to export file
            
        Returns:
            True if exported successfully
        """
        with self._lock:
            try:
                export_path = Path(file_path)
                export_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Configuration exported to {export_path}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error exporting configuration: {e}")
                return False
    
    def import_configuration(self, file_path: str) -> bool:
        """
        Import configuration from a file.
        
        Args:
            file_path: Path to import file
            
        Returns:
            True if imported successfully
        """
        with self._lock:
            try:
                import_path = Path(file_path)
                if not import_path.exists():
                    raise FileNotFoundError(f"Configuration file not found: {import_path}")
                
                with open(import_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate imported configuration
                temp_config = ApplicationConfig.from_dict(data)
                
                # Apply imported configuration
                self._config = temp_config
                self._config.last_updated = datetime.now().isoformat()
                
                success = self.save_configuration()
                if success:
                    self.logger.info(f"Configuration imported from {import_path}")
                
                return success
                
            except Exception as e:
                self.logger.error(f"Error importing configuration: {e}")
                return False


# Global configuration manager instance
_global_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """
    Get the global configuration manager instance.
    
    Returns:
        ConfigurationManager instance
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        _global_config_manager = ConfigurationManager()
    
    return _global_config_manager


def initialize_config_manager(config_file: Optional[str] = None) -> ConfigurationManager:
    """
    Initialize the global configuration manager with a specific config file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        ConfigurationManager instance
    """
    global _global_config_manager
    
    _global_config_manager = ConfigurationManager(config_file)
    return _global_config_manager


if __name__ == "__main__":
    # Demo usage
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Configuration Manager Demo")
    print("=" * 40)
    
    # Create configuration manager
    config_mgr = ConfigurationManager("demo_config.json")
    
    # Display current configuration
    config = config_mgr.get_config()
    print(f"Default input method: {config.user_preferences.default_input_method}")
    print(f"PDF annotation mode: {config.pdf_processing.default_annotation_mode}")
    print(f"Min text length: {config.text_validation.min_text_length}")
    print(f"API delay: {config.processing.api_delay_seconds}s")
    
    # Update some settings
    print("\nUpdating settings...")
    config_mgr.update_user_preferences(
        default_input_method="direct_text",
        auto_clear_chat_after_processing=False
    )
    
    config_mgr.update_pdf_processing_options(
        default_annotation_mode="sin",
        max_file_size_mb=100
    )
    
    # Display updated configuration
    config = config_mgr.get_config()
    print(f"Updated default input method: {config.user_preferences.default_input_method}")
    print(f"Updated PDF annotation mode: {config.pdf_processing.default_annotation_mode}")
    print(f"Updated max file size: {config.pdf_processing.max_file_size_mb} MB")
    
    # Validate configuration
    issues = config_mgr.validate_configuration()
    if issues:
        print(f"\nValidation issues: {issues}")
    else:
        print("\nConfiguration is valid!")
    
    # Test default input method
    default_mode = config_mgr.get_default_input_method()
    print(f"Default InputMode: {default_mode}")
    
    print("\nDemo completed successfully!")