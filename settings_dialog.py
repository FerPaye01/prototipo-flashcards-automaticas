"""
Settings Configuration Dialog

This module provides a GUI dialog for configuring application settings,
including user preferences, PDF processing options, text validation settings,
and processing configuration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional
import logging

from config_manager import ConfigurationManager, ApplicationConfig, ValidationLevel
from input_method_controller import InputMode


class SettingsDialog(tk.Toplevel):
    """
    Settings configuration dialog window.
    
    Provides a tabbed interface for configuring all application settings
    with validation and real-time preview of changes.
    """
    
    def __init__(self, parent, config_manager: ConfigurationManager):
        """
        Initialize settings dialog.
        
        Args:
            parent: Parent window
            config_manager: Configuration manager instance
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.original_config = config_manager.get_config()
        self.logger = logging.getLogger(__name__)
        
        # Dialog setup
        self.title("Flashcards Settings")
        self.geometry("600x500")
        self.minsize(500, 400)
        self.transient(parent)
        self.grab_set()
        
        # Center on parent
        self._center_on_parent(parent)
        
        # Variables for form fields
        self._create_variables()
        
        # Create UI
        self._create_widgets()
        
        # Load current settings
        self._load_current_settings()
        
        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    def _center_on_parent(self, parent):
        """Center dialog on parent window."""
        self.update_idletasks()
        
        # Get parent position and size
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        # Calculate center position
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.geometry(f"+{x}+{y}")
    
    def _create_variables(self):
        """Create tkinter variables for form fields."""
        # User Preferences
        self.default_input_method_var = tk.StringVar()
        self.remember_last_method_var = tk.BooleanVar()
        self.auto_clear_chat_var = tk.BooleanVar()
        self.show_progress_var = tk.BooleanVar()
        self.confirm_processing_var = tk.BooleanVar()
        
        # PDF Processing Options
        self.default_annotation_mode_var = tk.StringVar()
        self.extract_headers_footers_var = tk.BooleanVar()
        self.preserve_formatting_var = tk.BooleanVar()
        self.handle_multi_column_var = tk.BooleanVar()
        self.filter_page_numbers_var = tk.BooleanVar()
        self.min_annotation_length_var = tk.IntVar()
        self.max_file_size_var = tk.IntVar()
        
        # Text Validation Settings
        self.min_text_length_var = tk.IntVar()
        self.max_text_length_var = tk.IntVar()
        self.min_unique_chars_var = tk.IntVar()
        self.require_alphabetic_var = tk.BooleanVar()
        self.max_repetition_ratio_var = tk.DoubleVar()
        self.validation_level_var = tk.StringVar()
        
        # Processing Settings
        self.api_delay_var = tk.IntVar()
        self.max_retries_var = tk.IntVar()
        self.timeout_var = tk.IntVar()
        self.debug_logging_var = tk.BooleanVar()
        self.auto_import_anki_var = tk.BooleanVar()
        self.backup_flashcards_var = tk.BooleanVar()
    
    def _create_widgets(self):
        """Create the dialog widgets."""
        # Main container
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create tabs
        self._create_user_preferences_tab()
        self._create_pdf_processing_tab()
        self._create_text_validation_tab()
        self._create_processing_settings_tab()
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Buttons
        ttk.Button(button_frame, text="Reset to Defaults", command=self._reset_to_defaults).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Apply", command=self._on_apply).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=(5, 0))
    
    def _create_user_preferences_tab(self):
        """Create user preferences tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="User Preferences")
        
        # Scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Default Input Method
        input_group = ttk.LabelFrame(scrollable_frame, text="Default Input Method", padding=10)
        input_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_group, text="Default input method:").pack(anchor="w")
        input_combo = ttk.Combobox(
            input_group,
            textvariable=self.default_input_method_var,
            values=["pdf_annotations", "pdf_fulltext", "direct_text"],
            state="readonly"
        )
        input_combo.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Checkbutton(
            input_group,
            text="Remember last used input method",
            variable=self.remember_last_method_var
        ).pack(anchor="w", pady=(10, 0))
        
        # Interface Behavior
        behavior_group = ttk.LabelFrame(scrollable_frame, text="Interface Behavior", padding=10)
        behavior_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            behavior_group,
            text="Auto-clear chat after processing",
            variable=self.auto_clear_chat_var
        ).pack(anchor="w")
        
        ttk.Checkbutton(
            behavior_group,
            text="Show processing progress",
            variable=self.show_progress_var
        ).pack(anchor="w")
        
        ttk.Checkbutton(
            behavior_group,
            text="Confirm before processing",
            variable=self.confirm_processing_var
        ).pack(anchor="w")
        
        # Pack scrollable components
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_pdf_processing_tab(self):
        """Create PDF processing options tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="PDF Processing")
        
        # Scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Annotation Mode
        annotation_group = ttk.LabelFrame(scrollable_frame, text="Default Annotation Mode", padding=10)
        annotation_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Radiobutton(
            annotation_group,
            text="With annotations (con)",
            variable=self.default_annotation_mode_var,
            value="con"
        ).pack(anchor="w")
        
        ttk.Radiobutton(
            annotation_group,
            text="Without annotations (sin)",
            variable=self.default_annotation_mode_var,
            value="sin"
        ).pack(anchor="w")
        
        # Extraction Options
        extraction_group = ttk.LabelFrame(scrollable_frame, text="Text Extraction Options", padding=10)
        extraction_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            extraction_group,
            text="Extract headers and footers",
            variable=self.extract_headers_footers_var
        ).pack(anchor="w")
        
        ttk.Checkbutton(
            extraction_group,
            text="Preserve text formatting",
            variable=self.preserve_formatting_var
        ).pack(anchor="w")
        
        ttk.Checkbutton(
            extraction_group,
            text="Handle multi-column layouts",
            variable=self.handle_multi_column_var
        ).pack(anchor="w")
        
        ttk.Checkbutton(
            extraction_group,
            text="Filter out page numbers",
            variable=self.filter_page_numbers_var
        ).pack(anchor="w")
        
        # Limits
        limits_group = ttk.LabelFrame(scrollable_frame, text="Processing Limits", padding=10)
        limits_group.pack(fill=tk.X, pady=(0, 10))
        
        # Min annotation length
        ttk.Label(limits_group, text="Minimum annotation length (characters):").pack(anchor="w")
        ttk.Spinbox(
            limits_group,
            from_=1,
            to=1000,
            textvariable=self.min_annotation_length_var,
            width=10
        ).pack(anchor="w", pady=(2, 10))
        
        # Max file size
        ttk.Label(limits_group, text="Maximum file size (MB):").pack(anchor="w")
        ttk.Spinbox(
            limits_group,
            from_=1,
            to=500,
            textvariable=self.max_file_size_var,
            width=10
        ).pack(anchor="w", pady=(2, 0))
        
        # Pack scrollable components
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_text_validation_tab(self):
        """Create text validation settings tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Text Validation")
        
        # Scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Text Length Limits
        length_group = ttk.LabelFrame(scrollable_frame, text="Text Length Limits", padding=10)
        length_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(length_group, text="Minimum text length (characters):").pack(anchor="w")
        ttk.Spinbox(
            length_group,
            from_=1,
            to=1000,
            textvariable=self.min_text_length_var,
            width=10
        ).pack(anchor="w", pady=(2, 10))
        
        ttk.Label(length_group, text="Maximum text length (characters):").pack(anchor="w")
        ttk.Spinbox(
            length_group,
            from_=100,
            to=100000,
            textvariable=self.max_text_length_var,
            width=10
        ).pack(anchor="w", pady=(2, 0))
        
        # Content Validation
        content_group = ttk.LabelFrame(scrollable_frame, text="Content Validation", padding=10)
        content_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(content_group, text="Minimum unique characters:").pack(anchor="w")
        ttk.Spinbox(
            content_group,
            from_=1,
            to=50,
            textvariable=self.min_unique_chars_var,
            width=10
        ).pack(anchor="w", pady=(2, 10))
        
        ttk.Checkbutton(
            content_group,
            text="Require alphabetic content",
            variable=self.require_alphabetic_var
        ).pack(anchor="w", pady=(0, 10))
        
        ttk.Label(content_group, text="Maximum repetition ratio (0.0-1.0):").pack(anchor="w")
        ttk.Spinbox(
            content_group,
            from_=0.0,
            to=1.0,
            increment=0.1,
            textvariable=self.max_repetition_ratio_var,
            width=10,
            format="%.1f"
        ).pack(anchor="w", pady=(2, 0))
        
        # Validation Level
        level_group = ttk.LabelFrame(scrollable_frame, text="Validation Level", padding=10)
        level_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(level_group, text="Validation strictness:").pack(anchor="w")
        level_combo = ttk.Combobox(
            level_group,
            textvariable=self.validation_level_var,
            values=[level.value for level in ValidationLevel],
            state="readonly"
        )
        level_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Pack scrollable components
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_processing_settings_tab(self):
        """Create processing settings tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Processing")
        
        # Scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # API Settings
        api_group = ttk.LabelFrame(scrollable_frame, text="API Settings", padding=10)
        api_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(api_group, text="API delay between calls (seconds):").pack(anchor="w")
        ttk.Spinbox(
            api_group,
            from_=0,
            to=300,
            textvariable=self.api_delay_var,
            width=10
        ).pack(anchor="w", pady=(2, 10))
        
        ttk.Label(api_group, text="Maximum retries:").pack(anchor="w")
        ttk.Spinbox(
            api_group,
            from_=0,
            to=10,
            textvariable=self.max_retries_var,
            width=10
        ).pack(anchor="w", pady=(2, 10))
        
        ttk.Label(api_group, text="Timeout per operation (seconds):").pack(anchor="w")
        ttk.Spinbox(
            api_group,
            from_=30,
            to=1800,
            textvariable=self.timeout_var,
            width=10
        ).pack(anchor="w", pady=(2, 0))
        
        # Processing Options
        processing_group = ttk.LabelFrame(scrollable_frame, text="Processing Options", padding=10)
        processing_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            processing_group,
            text="Enable debug logging",
            variable=self.debug_logging_var
        ).pack(anchor="w")
        
        ttk.Checkbutton(
            processing_group,
            text="Auto-import to Anki",
            variable=self.auto_import_anki_var
        ).pack(anchor="w")
        
        ttk.Checkbutton(
            processing_group,
            text="Backup flashcards",
            variable=self.backup_flashcards_var
        ).pack(anchor="w")
        
        # Pack scrollable components
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _load_current_settings(self):
        """Load current settings into form fields."""
        config = self.config_manager.get_config()
        
        # User Preferences
        prefs = config.user_preferences
        self.default_input_method_var.set(prefs.default_input_method)
        self.remember_last_method_var.set(prefs.remember_last_input_method)
        self.auto_clear_chat_var.set(prefs.auto_clear_chat_after_processing)
        self.show_progress_var.set(prefs.show_processing_progress)
        self.confirm_processing_var.set(prefs.confirm_before_processing)
        
        # PDF Processing Options
        pdf_opts = config.pdf_processing
        self.default_annotation_mode_var.set(pdf_opts.default_annotation_mode)
        self.extract_headers_footers_var.set(pdf_opts.extract_headers_footers)
        self.preserve_formatting_var.set(pdf_opts.preserve_formatting)
        self.handle_multi_column_var.set(pdf_opts.handle_multi_column)
        self.filter_page_numbers_var.set(pdf_opts.filter_page_numbers)
        self.min_annotation_length_var.set(pdf_opts.min_annotation_length)
        self.max_file_size_var.set(pdf_opts.max_file_size_mb)
        
        # Text Validation Settings
        text_val = config.text_validation
        self.min_text_length_var.set(text_val.min_text_length)
        self.max_text_length_var.set(text_val.max_text_length)
        self.min_unique_chars_var.set(text_val.min_unique_characters)
        self.require_alphabetic_var.set(text_val.require_alphabetic_content)
        self.max_repetition_ratio_var.set(text_val.max_repetition_ratio)
        self.validation_level_var.set(text_val.validation_level)
        
        # Processing Settings
        proc_settings = config.processing
        self.api_delay_var.set(proc_settings.api_delay_seconds)
        self.max_retries_var.set(proc_settings.max_retries)
        self.timeout_var.set(proc_settings.timeout_seconds)
        self.debug_logging_var.set(proc_settings.enable_debug_logging)
        self.auto_import_anki_var.set(proc_settings.auto_import_to_anki)
        self.backup_flashcards_var.set(proc_settings.backup_flashcards)
    
    def _validate_settings(self) -> bool:
        """
        Validate current settings.
        
        Returns:
            True if settings are valid, False otherwise
        """
        try:
            # Validate text length limits
            min_length = self.min_text_length_var.get()
            max_length = self.max_text_length_var.get()
            
            if min_length >= max_length:
                messagebox.showerror(
                    "Validation Error",
                    "Maximum text length must be greater than minimum text length."
                )
                return False
            
            # Validate repetition ratio
            repetition_ratio = self.max_repetition_ratio_var.get()
            if not (0.0 <= repetition_ratio <= 1.0):
                messagebox.showerror(
                    "Validation Error",
                    "Maximum repetition ratio must be between 0.0 and 1.0."
                )
                return False
            
            # Validate file size limits
            min_annotation = self.min_annotation_length_var.get()
            max_file_size = self.max_file_size_var.get()
            
            if min_annotation < 1:
                messagebox.showerror(
                    "Validation Error",
                    "Minimum annotation length must be at least 1."
                )
                return False
            
            if max_file_size < 1:
                messagebox.showerror(
                    "Validation Error",
                    "Maximum file size must be at least 1 MB."
                )
                return False
            
            # Validate processing settings
            timeout = self.timeout_var.get()
            if timeout < 30:
                messagebox.showerror(
                    "Validation Error",
                    "Timeout must be at least 30 seconds."
                )
                return False
            
            return True
            
        except Exception as e:
            messagebox.showerror("Validation Error", f"Settings validation failed: {e}")
            return False
    
    def _apply_settings(self) -> bool:
        """
        Apply current settings to configuration.
        
        Returns:
            True if applied successfully, False otherwise
        """
        if not self._validate_settings():
            return False
        
        try:
            # Update user preferences
            self.config_manager.update_user_preferences(
                default_input_method=self.default_input_method_var.get(),
                remember_last_input_method=self.remember_last_method_var.get(),
                auto_clear_chat_after_processing=self.auto_clear_chat_var.get(),
                show_processing_progress=self.show_progress_var.get(),
                confirm_before_processing=self.confirm_processing_var.get()
            )
            
            # Update PDF processing options
            self.config_manager.update_pdf_processing_options(
                default_annotation_mode=self.default_annotation_mode_var.get(),
                extract_headers_footers=self.extract_headers_footers_var.get(),
                preserve_formatting=self.preserve_formatting_var.get(),
                handle_multi_column=self.handle_multi_column_var.get(),
                filter_page_numbers=self.filter_page_numbers_var.get(),
                min_annotation_length=self.min_annotation_length_var.get(),
                max_file_size_mb=self.max_file_size_var.get()
            )
            
            # Update text validation settings
            self.config_manager.update_text_validation_settings(
                min_text_length=self.min_text_length_var.get(),
                max_text_length=self.max_text_length_var.get(),
                min_unique_characters=self.min_unique_chars_var.get(),
                require_alphabetic_content=self.require_alphabetic_var.get(),
                max_repetition_ratio=self.max_repetition_ratio_var.get(),
                validation_level=self.validation_level_var.get()
            )
            
            # Update processing settings
            self.config_manager.update_processing_settings(
                api_delay_seconds=self.api_delay_var.get(),
                max_retries=self.max_retries_var.get(),
                timeout_seconds=self.timeout_var.get(),
                enable_debug_logging=self.debug_logging_var.get(),
                auto_import_to_anki=self.auto_import_anki_var.get(),
                backup_flashcards=self.backup_flashcards_var.get()
            )
            
            return True
            
        except Exception as e:
            messagebox.showerror("Apply Error", f"Failed to apply settings: {e}")
            return False
    
    def _reset_to_defaults(self):
        """Reset all settings to default values."""
        if messagebox.askyesno(
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?"
        ):
            # Reset configuration manager
            if self.config_manager.reset_to_defaults():
                # Reload settings into form
                self._load_current_settings()
                messagebox.showinfo("Reset Complete", "Settings have been reset to default values.")
            else:
                messagebox.showerror("Reset Error", "Failed to reset settings to defaults.")
    
    def _on_ok(self):
        """Handle OK button click."""
        if self._apply_settings():
            self.destroy()
    
    def _on_apply(self):
        """Handle Apply button click."""
        if self._apply_settings():
            messagebox.showinfo("Settings Applied", "Settings have been applied successfully.")
    
    def _on_cancel(self):
        """Handle Cancel button click."""
        # Check if settings have changed
        if self._settings_changed():
            if messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to cancel?"
            ):
                self.destroy()
        else:
            self.destroy()
    
    def _settings_changed(self) -> bool:
        """
        Check if settings have been modified.
        
        Returns:
            True if settings have changed, False otherwise
        """
        try:
            current_config = self.config_manager.get_config()
            
            # Compare user preferences
            prefs = current_config.user_preferences
            if (self.default_input_method_var.get() != prefs.default_input_method or
                self.remember_last_method_var.get() != prefs.remember_last_input_method or
                self.auto_clear_chat_var.get() != prefs.auto_clear_chat_after_processing or
                self.show_progress_var.get() != prefs.show_processing_progress or
                self.confirm_processing_var.get() != prefs.confirm_before_processing):
                return True
            
            # Compare PDF processing options
            pdf_opts = current_config.pdf_processing
            if (self.default_annotation_mode_var.get() != pdf_opts.default_annotation_mode or
                self.extract_headers_footers_var.get() != pdf_opts.extract_headers_footers or
                self.preserve_formatting_var.get() != pdf_opts.preserve_formatting or
                self.handle_multi_column_var.get() != pdf_opts.handle_multi_column or
                self.filter_page_numbers_var.get() != pdf_opts.filter_page_numbers or
                self.min_annotation_length_var.get() != pdf_opts.min_annotation_length or
                self.max_file_size_var.get() != pdf_opts.max_file_size_mb):
                return True
            
            # Compare text validation settings
            text_val = current_config.text_validation
            if (self.min_text_length_var.get() != text_val.min_text_length or
                self.max_text_length_var.get() != text_val.max_text_length or
                self.min_unique_chars_var.get() != text_val.min_unique_characters or
                self.require_alphabetic_var.get() != text_val.require_alphabetic_content or
                abs(self.max_repetition_ratio_var.get() - text_val.max_repetition_ratio) > 0.01 or
                self.validation_level_var.get() != text_val.validation_level):
                return True
            
            # Compare processing settings
            proc_settings = current_config.processing
            if (self.api_delay_var.get() != proc_settings.api_delay_seconds or
                self.max_retries_var.get() != proc_settings.max_retries or
                self.timeout_var.get() != proc_settings.timeout_seconds or
                self.debug_logging_var.get() != proc_settings.enable_debug_logging or
                self.auto_import_anki_var.get() != proc_settings.auto_import_to_anki or
                self.backup_flashcards_var.get() != proc_settings.backup_flashcards):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking for setting changes: {e}")
            return False


if __name__ == "__main__":
    # Demo usage
    import logging
    from config_manager import get_config_manager
    
    logging.basicConfig(level=logging.INFO)
    
    # Create demo window
    root = tk.Tk()
    root.title("Settings Dialog Demo")
    root.geometry("400x300")
    
    config_mgr = get_config_manager()
    
    def open_settings():
        dialog = SettingsDialog(root, config_mgr)
        root.wait_window(dialog)
    
    ttk.Button(root, text="Open Settings", command=open_settings).pack(pady=50)
    
    root.mainloop()