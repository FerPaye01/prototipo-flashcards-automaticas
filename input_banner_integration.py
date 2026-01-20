"""
Input Banner Integration Module

This module provides integration between the InputBanner component,
InputMethodController, and the main FlashcardsGUI application.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
import logging

from input_banner import InputBanner
from input_method_controller import InputMethodController, InputMode, string_to_input_mode


class InputBannerIntegration:
    """
    Integration class that connects InputBanner with InputMethodController
    and provides seamless integration with the main GUI application.
    """
    
    def __init__(self, parent_widget, main_gui_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the input banner integration.
        
        Args:
            parent_widget: Parent tkinter widget where banner will be placed
            main_gui_callback: Callback function to notify main GUI of mode changes
        """
        self.parent = parent_widget
        self.main_gui_callback = main_gui_callback
        
        # Initialize controller
        self.controller = InputMethodController()
        
        # Initialize banner with controller callback
        self.banner = InputBanner(parent_widget, self._on_banner_mode_selected)
        
        # Register controller callbacks
        self.controller.register_mode_change_callback(
            "banner_integration", 
            self._on_controller_mode_changed
        )
        
        self.controller.register_validation_callback(
            "banner_integration",
            self._validate_mode_transition
        )
        
        # Register UI components with controller
        self.controller.register_ui_component("input_banner", self.banner)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Sync initial state
        self._sync_banner_with_controller()
    
    def _on_banner_mode_selected(self, mode_string: str):
        """
        Handle mode selection from banner component.
        
        Args:
            mode_string: Selected mode as string
        """
        try:
            new_mode = string_to_input_mode(mode_string)
            success = self.controller.switch_input_mode(new_mode)
            
            if not success:
                # Revert banner to current controller mode if switch failed
                self._sync_banner_with_controller()
                
        except ValueError as e:
            self.logger.error(f"Invalid mode selected from banner: {mode_string}")
            # Revert to current mode
            self._sync_banner_with_controller()
    
    def _on_controller_mode_changed(self, old_mode: InputMode, new_mode: InputMode):
        """
        Handle mode change from controller.
        
        Args:
            old_mode: Previous mode
            new_mode: New mode
        """
        # Notify main GUI if callback is provided
        if self.main_gui_callback:
            try:
                self.main_gui_callback(new_mode.value)
            except Exception as e:
                self.logger.error(f"Error in main GUI callback: {e}")
        
        # Log the change
        self.logger.info(f"Input method changed: {old_mode.value} -> {new_mode.value}")
    
    def _validate_mode_transition(self, old_mode: InputMode, new_mode: InputMode) -> bool:
        """
        Validate mode transitions for banner integration.
        
        Args:
            old_mode: Current mode
            new_mode: Target mode
            
        Returns:
            True if transition is valid
        """
        is_valid, error_msg = self.controller.validate_mode_transition(old_mode, new_mode)
        
        if not is_valid:
            self.logger.warning(f"Mode transition blocked: {error_msg}")
            # Could show user notification here if needed
        
        return is_valid
    
    def _sync_banner_with_controller(self):
        """Synchronize banner display with controller state."""
        current_mode = self.controller.get_current_mode()
        self.banner.set_active_mode(current_mode.value)
    
    def get_banner_widget(self) -> InputBanner:
        """
        Get the banner widget for layout management.
        
        Returns:
            InputBanner widget instance
        """
        return self.banner
    
    def get_controller(self) -> InputMethodController:
        """
        Get the input method controller.
        
        Returns:
            InputMethodController instance
        """
        return self.controller
    
    def get_current_mode(self) -> str:
        """
        Get the current input mode as string.
        
        Returns:
            Current mode string
        """
        return self.controller.get_current_mode().value
    
    def set_mode(self, mode_string: str, force: bool = False) -> bool:
        """
        Programmatically set the input mode.
        
        Args:
            mode_string: Mode to set
            force: Force the change without validation
            
        Returns:
            True if mode was set successfully
        """
        try:
            new_mode = string_to_input_mode(mode_string)
            return self.controller.switch_input_mode(new_mode, force)
        except ValueError:
            self.logger.error(f"Invalid mode string: {mode_string}")
            return False
    
    def set_processing_state(self, is_processing: bool):
        """
        Set processing state to control mode switching.
        
        Args:
            is_processing: True if processing is in progress
        """
        self.controller.set_processing_state(is_processing)
        
        # Update banner visual state
        for button in self.banner.mode_buttons.values():
            state = "disabled" if is_processing else "normal"
            button.configure(state=state)
    
    def register_ui_component(self, name: str, component):
        """
        Register additional UI components with the controller.
        
        Args:
            name: Component name
            component: UI component instance
        """
        self.controller.register_ui_component(name, component)
    
    def register_mode_change_callback(self, name: str, callback: Callable[[InputMode, InputMode], None]):
        """
        Register a callback for mode changes.
        
        Args:
            name: Callback name
            callback: Function to call on mode change
        """
        self.controller.register_mode_change_callback(name, callback)
    
    def pack(self, **kwargs):
        """Pack the banner widget with given options."""
        self.banner.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the banner widget with given options."""
        self.banner.grid(**kwargs)
    
    def place(self, **kwargs):
        """Place the banner widget with given options."""
        self.banner.place(**kwargs)


# Demo application
if __name__ == "__main__":
    def demo_main_gui_callback(mode: str):
        print(f"Main GUI notified of mode change: {mode}")
        demo_label.configure(text=f"Current Mode: {mode.replace('_', ' ').title()}")
    
    # Create demo window
    root = tk.Tk()
    root.title("Input Banner Integration Demo")
    root.geometry("900x400")
    
    # Create integration
    integration = InputBannerIntegration(root, demo_main_gui_callback)
    integration.pack(fill=tk.X, padx=20, pady=20)
    
    # Add demo content
    demo_frame = ttk.Frame(root)
    demo_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    demo_label = ttk.Label(
        demo_frame,
        text=f"Current Mode: {integration.get_current_mode().replace('_', ' ').title()}",
        font=("TkDefaultFont", 14, "bold")
    )
    demo_label.pack(pady=20)
    
    # Add control buttons for testing
    control_frame = ttk.Frame(demo_frame)
    control_frame.pack(pady=10)
    
    ttk.Button(
        control_frame,
        text="Simulate Processing",
        command=lambda: integration.set_processing_state(True)
    ).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(
        control_frame,
        text="Stop Processing",
        command=lambda: integration.set_processing_state(False)
    ).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(
        control_frame,
        text="Force PDF Mode",
        command=lambda: integration.set_mode("pdf_annotations", force=True)
    ).pack(side=tk.LEFT, padx=5)
    
    root.mainloop()