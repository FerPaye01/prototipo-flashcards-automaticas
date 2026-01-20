"""
Input Method Controller for Flashcards UI Enhancement

This module provides the InputMethodController class that manages
input method switching logic, UI state management, and validation
for input method transitions.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Dict, Any, Tuple
from enum import Enum
import logging


class InputMode(Enum):
    """Enumeration of available input modes."""
    PDF_ANNOTATIONS = "pdf_annotations"
    PDF_FULLTEXT = "pdf_fulltext"
    DIRECT_TEXT = "direct_text"
    ANKI_SYNC = "anki_sync"


class InputMethodController:
    """
    Controller class that manages input method switching and UI state.
    
    Handles:
    - Input method selection and validation
    - UI state transitions
    - Callback management for mode changes
    - Validation of input method transitions
    """
    
    def __init__(self):
        """Initialize the input method controller."""
        self.current_mode = InputMode.PDF_ANNOTATIONS
        self.previous_mode = None
        
        # Callback registry
        self.mode_change_callbacks: Dict[str, Callable[[InputMode, InputMode], None]] = {}
        self.validation_callbacks: Dict[str, Callable[[InputMode, InputMode], bool]] = {}
        
        # UI state tracking
        self.ui_components: Dict[str, Any] = {}
        self.is_processing = False
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def register_mode_change_callback(self, name: str, callback: Callable[[InputMode, InputMode], None]):
        """
        Register a callback to be called when input mode changes.
        
        Args:
            name: Unique name for the callback
            callback: Function to call with (old_mode, new_mode) parameters
        """
        self.mode_change_callbacks[name] = callback
    
    def register_validation_callback(self, name: str, callback: Callable[[InputMode, InputMode], bool]):
        """
        Register a validation callback for mode transitions.
        
        Args:
            name: Unique name for the callback
            callback: Function that returns True if transition is valid
        """
        self.validation_callbacks[name] = callback
    
    def register_ui_component(self, name: str, component: Any):
        """
        Register a UI component for state management.
        
        Args:
            name: Unique name for the component
            component: UI component instance
        """
        self.ui_components[name] = component
    
    def switch_input_mode(self, new_mode: InputMode, force: bool = False) -> bool:
        """
        Switch to a new input mode with validation.
        
        Args:
            new_mode: Target input mode
            force: Skip validation if True
            
        Returns:
            True if mode switch was successful, False otherwise
        """
        if new_mode == self.current_mode:
            self.logger.debug(f"Already in mode {new_mode.value}")
            return True
        
        # Check if processing is in progress
        if self.is_processing and not force:
            messagebox.showwarning(
                "Processing in Progress",
                "Cannot change input method while processing is in progress. "
                "Please wait for current operation to complete."
            )
            return False
        
        old_mode = self.current_mode
        
        # Run validation callbacks
        if not force:
            for name, validator in self.validation_callbacks.items():
                try:
                    if not validator(old_mode, new_mode):
                        self.logger.warning(f"Validation failed for transition {old_mode.value} -> {new_mode.value} (validator: {name})")
                        return False
                except Exception as e:
                    self.logger.error(f"Error in validation callback {name}: {e}")
                    return False
        
        # Perform the mode switch
        try:
            self.previous_mode = self.current_mode
            self.current_mode = new_mode
            
            # Update UI state
            self._update_ui_state(old_mode, new_mode)
            
            # Notify callbacks
            self._notify_mode_change_callbacks(old_mode, new_mode)
            
            self.logger.info(f"Successfully switched from {old_mode.value} to {new_mode.value}")
            return True
            
        except Exception as e:
            # Rollback on error
            self.current_mode = old_mode
            self.logger.error(f"Error switching modes: {e}")
            messagebox.showerror(
                "Mode Switch Error",
                f"Failed to switch input method: {str(e)}"
            )
            return False
    
    def _update_ui_state(self, old_mode: InputMode, new_mode: InputMode):
        """
        Update UI components based on mode change.
        
        Args:
            old_mode: Previous input mode
            new_mode: New input mode
        """
        # Update input banner if registered
        if "input_banner" in self.ui_components:
            banner = self.ui_components["input_banner"]
            if hasattr(banner, "set_active_mode"):
                banner.set_active_mode(new_mode.value)
        
        # Show/hide relevant UI sections
        self._toggle_ui_sections(old_mode, new_mode)
        
        # Update button states and labels
        self._update_control_states(new_mode)
    
    def _toggle_ui_sections(self, old_mode: InputMode, new_mode: InputMode):
        """
        Show/hide UI sections based on active mode.
        
        Args:
            old_mode: Previous input mode
            new_mode: New input mode
        """
        # Hide old mode UI elements
        old_section_name = f"{old_mode.value}_section"
        if old_section_name in self.ui_components:
            old_section = self.ui_components[old_section_name]
            if hasattr(old_section, "pack_forget"):
                old_section.pack_forget()
            elif hasattr(old_section, "grid_forget"):
                old_section.grid_forget()
        
        # Show new mode UI elements
        new_section_name = f"{new_mode.value}_section"
        if new_section_name in self.ui_components:
            new_section = self.ui_components[new_section_name]
            if hasattr(new_section, "pack"):
                new_section.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            elif hasattr(new_section, "grid"):
                new_section.grid(sticky="nsew")
    
    def _update_control_states(self, new_mode: InputMode):
        """
        Update control button states based on active mode.
        
        Args:
            new_mode: Current input mode
        """
        # Update process button text based on mode
        if "process_button" in self.ui_components:
            button = self.ui_components["process_button"]
            if hasattr(button, "configure"):
                if new_mode == InputMode.PDF_ANNOTATIONS:
                    button.configure(text="Process PDF Annotations")
                elif new_mode == InputMode.PDF_FULLTEXT:
                    button.configure(text="Process PDF Full Text")
                elif new_mode == InputMode.DIRECT_TEXT:
                    button.configure(text="Process Text Input")
                elif new_mode == InputMode.ANKI_SYNC:
                    button.configure(text="Sync to Anki")
        
        # Update file selection controls
        if "file_controls" in self.ui_components:
            controls = self.ui_components["file_controls"]
            if new_mode in [InputMode.PDF_ANNOTATIONS, InputMode.PDF_FULLTEXT]:
                # Show file selection controls
                if hasattr(controls, "pack"):
                    controls.pack(fill=tk.X, padx=6, pady=6)
            else:
                # Hide file selection controls for direct text input and anki sync
                if hasattr(controls, "pack_forget"):
                    controls.pack_forget()
    
    def _notify_mode_change_callbacks(self, old_mode: InputMode, new_mode: InputMode):
        """
        Notify all registered callbacks about mode change.
        
        Args:
            old_mode: Previous input mode
            new_mode: New input mode
        """
        for name, callback in self.mode_change_callbacks.items():
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                self.logger.error(f"Error in mode change callback {name}: {e}")
    
    def get_current_mode(self) -> InputMode:
        """
        Get the current input mode.
        
        Returns:
            Current InputMode
        """
        return self.current_mode
    
    def get_previous_mode(self) -> Optional[InputMode]:
        """
        Get the previous input mode.
        
        Returns:
            Previous InputMode or None if no previous mode
        """
        return self.previous_mode
    
    def set_processing_state(self, is_processing: bool):
        """
        Set the processing state to control mode switching.
        
        Args:
            is_processing: True if processing is in progress
        """
        self.is_processing = is_processing
        
        # Update UI to reflect processing state
        # Note: UI state updates are handled by the integration layer
    
    def validate_mode_transition(self, from_mode: InputMode, to_mode: InputMode) -> Tuple[bool, str]:
        """
        Validate if a mode transition is allowed.
        
        Args:
            from_mode: Source mode
            to_mode: Target mode
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check processing state
        if self.is_processing:
            return False, "Cannot change mode while processing is in progress"
        
        # Check if there's unsaved content
        if from_mode == InputMode.DIRECT_TEXT:
            if "chat_interface" in self.ui_components:
                chat = self.ui_components["chat_interface"]
                if hasattr(chat, "has_unsaved_content") and chat.has_unsaved_content():
                    return False, "You have unsaved text content. Please process or clear it first."
        
        # Check if files are selected for PDF modes
        if to_mode in [InputMode.PDF_ANNOTATIONS, InputMode.PDF_FULLTEXT]:
            if "file_list" in self.ui_components:
                file_list = self.ui_components["file_list"]
                if hasattr(file_list, "get_file_count") and file_list.get_file_count() == 0:
                    # This is just a warning, not a blocking condition
                    pass
        
        return True, ""
    
    def reset_to_default(self):
        """Reset controller to default state."""
        self.switch_input_mode(InputMode.PDF_ANNOTATIONS, force=True)
        self.previous_mode = None
        self.is_processing = False


# Utility functions for mode conversion
def string_to_input_mode(mode_string: str) -> InputMode:
    """
    Convert string to InputMode enum.
    
    Args:
        mode_string: String representation of mode
        
    Returns:
        InputMode enum value
        
    Raises:
        ValueError: If mode_string is not valid
    """
    mode_map = {
        "pdf_annotations": InputMode.PDF_ANNOTATIONS,
        "pdf_fulltext": InputMode.PDF_FULLTEXT,
        "direct_text": InputMode.DIRECT_TEXT,
        "anki_sync": InputMode.ANKI_SYNC
    }
    
    if mode_string not in mode_map:
        raise ValueError(f"Invalid mode string: {mode_string}")
    
    return mode_map[mode_string]


def input_mode_to_string(mode: InputMode) -> str:
    """
    Convert InputMode enum to string.
    
    Args:
        mode: InputMode enum value
        
    Returns:
        String representation of mode
    """
    return mode.value


# Demo/Test functions
if __name__ == "__main__":
    # Demo application
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    def demo_mode_change_callback(old_mode: InputMode, new_mode: InputMode):
        print(f"Mode changed: {old_mode.value} -> {new_mode.value}")
    
    def demo_validation_callback(old_mode: InputMode, new_mode: InputMode) -> bool:
        print(f"Validating transition: {old_mode.value} -> {new_mode.value}")
        return True  # Allow all transitions in demo
    
    # Create controller
    controller = InputMethodController()
    controller.register_mode_change_callback("demo", demo_mode_change_callback)
    controller.register_validation_callback("demo", demo_validation_callback)
    
    # Test mode switching
    print("Testing mode switching...")
    controller.switch_input_mode(InputMode.PDF_FULLTEXT)
    controller.switch_input_mode(InputMode.DIRECT_TEXT)
    controller.switch_input_mode(InputMode.PDF_ANNOTATIONS)
    
    print(f"Current mode: {controller.get_current_mode().value}")
    print(f"Previous mode: {controller.get_previous_mode().value if controller.get_previous_mode() else 'None'}")