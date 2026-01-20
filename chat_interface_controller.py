"""
Chat Interface Controller

This module provides the controller that connects the ChatInterface component
with the direct text processing workflow and integrates with the main GUI.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import Optional, Callable, Dict, Any
from chat_interface import ChatInterface
from direct_text_processor import DirectTextIntegration


class ChatInterfaceController:
    """
    Controller that manages the ChatInterface and connects it to the processing pipeline.
    
    Provides:
    - Integration between UI and processing logic
    - Progress tracking and user feedback
    - Error handling and recovery
    - Thread management for non-blocking processing
    """
    
    def __init__(self, parent_widget, main_gui_callback: Optional[Callable] = None):
        """
        Initialize the chat interface controller.
        
        Args:
            parent_widget: Parent tkinter widget
            main_gui_callback: Callback to notify main GUI of processing events
        """
        self.parent = parent_widget
        self.main_gui_callback = main_gui_callback
        
        # Initialize processing integration
        self.text_processor = DirectTextIntegration()
        
        # Initialize chat interface with validation callback
        self.chat_interface = ChatInterface(
            parent_widget, 
            validation_callback=self._validate_text_content
        )
        
        # Connect process button to controller
        self.chat_interface.process_button.configure(command=self._on_process_clicked)
        
        # Processing state
        self.processing_thread = None
        self.is_processing = False
        self.last_result = None
        
        # Progress tracking
        self.progress_window = None
        self.progress_var = None
        self.progress_label_var = None
    
    def _validate_text_content(self, text: str) -> bool:
        """
        Custom validation for text content.
        
        Args:
            text: Text to validate
            
        Returns:
            True if text is valid for processing
        """
        is_valid, _ = self.text_processor.validate_input(text)
        return is_valid
    
    def _on_process_clicked(self):
        """Handle process button click."""
        if self.is_processing:
            return
        
        text = self.chat_interface.get_text()
        if not text:
            messagebox.showwarning("No Text", "Please enter text to process.")
            return
        
        # Final validation
        is_valid, error_msg = self.text_processor.validate_input(text)
        if not is_valid:
            messagebox.showerror("Invalid Input", f"Cannot process text: {error_msg}")
            return
        
        # Confirm processing
        char_count = len(text)
        word_count = len(text.split())
        
        confirm_msg = (
            f"Process this text for flashcard generation?\n\n"
            f"Characters: {char_count:,}\n"
            f"Words: {word_count:,}\n\n"
            f"This may take several minutes depending on content length."
        )
        
        if not messagebox.askyesno("Confirm Processing", confirm_msg):
            return
        
        # Start processing in background thread
        self._start_processing(text)
    
    def _start_processing(self, text: str):
        """
        Start text processing in background thread.
        
        Args:
            text: Text to process
        """
        self.is_processing = True
        self.chat_interface.set_processing_state(True)
        
        # Show progress window
        self._show_progress_window()
        
        # Notify main GUI
        if self.main_gui_callback:
            try:
                self.main_gui_callback("processing_started", {"text_length": len(text)})
            except Exception:
                pass  # Don't fail if callback has issues
        
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._process_text_thread,
            args=(text,),
            daemon=True
        )
        self.processing_thread.start()
    
    def _process_text_thread(self, text: str):
        """
        Background thread for text processing.
        
        Args:
            text: Text to process
        """
        try:
            # Process with progress updates
            result = self.text_processor.process_with_progress(
                text, 
                self._update_progress
            )
            
            # Store result
            self.last_result = result
            
            # Schedule UI update on main thread
            self.parent.after(0, self._on_processing_complete, result)
            
        except Exception as e:
            # Handle unexpected errors
            error_result = {
                'success': False,
                'error': str(e),
                'flashcard_count': 0,
                'processing_time': 0
            }
            self.parent.after(0, self._on_processing_complete, error_result)
    
    def _update_progress(self, state: Dict[str, Any]):
        """
        Update progress display from processing thread.
        
        Args:
            state: Processing state dictionary
        """
        # Schedule UI update on main thread
        self.parent.after(0, self._update_progress_ui, state)
    
    def _update_progress_ui(self, state: Dict[str, Any]):
        """
        Update progress UI on main thread.
        
        Args:
            state: Processing state dictionary
        """
        if not self.progress_window or not self.progress_window.winfo_exists():
            return
        
        progress = state.get('progress', 0)
        total_steps = state.get('total_steps', 5)
        current_step = state.get('current_step', 'Processing...')
        error = state.get('error')
        
        if error:
            self.progress_label_var.set(f"Error: {error}")
            return
        
        # Update progress bar
        progress_percent = (progress / total_steps) * 100
        self.progress_var.set(progress_percent)
        
        # Update label
        self.progress_label_var.set(f"Step {progress}/{total_steps}: {current_step}")
    
    def _show_progress_window(self):
        """Show progress tracking window."""
        self.progress_window = tk.Toplevel(self.parent)
        self.progress_window.title("Processing Text")
        self.progress_window.geometry("400x150")
        self.progress_window.transient(self.parent)
        self.progress_window.grab_set()
        
        # Center the window
        self.progress_window.update_idletasks()
        x = (self.progress_window.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.progress_window.winfo_screenheight() // 2) - (150 // 2)
        self.progress_window.geometry(f"400x150+{x}+{y}")
        
        # Create progress widgets
        frame = ttk.Frame(self.progress_window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Processing text for flashcard generation...", 
                 font=("TkDefaultFont", 10, "bold")).pack(pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            frame, 
            variable=self.progress_var, 
            maximum=100,
            length=300
        )
        progress_bar.pack(pady=(0, 10))
        
        self.progress_label_var = tk.StringVar(value="Initializing...")
        ttk.Label(frame, textvariable=self.progress_label_var).pack()
        
        # Cancel button
        ttk.Button(
            frame, 
            text="Cancel", 
            command=self._cancel_processing
        ).pack(pady=(10, 0))
        
        # Handle window close
        self.progress_window.protocol("WM_DELETE_WINDOW", self._cancel_processing)
    
    def _cancel_processing(self):
        """Cancel current processing operation."""
        if self.is_processing:
            self.text_processor.cancel_processing()
            self.is_processing = False
            self.chat_interface.set_processing_state(False)
            
            if self.progress_window and self.progress_window.winfo_exists():
                self.progress_window.destroy()
            
            # Notify main GUI
            if self.main_gui_callback:
                try:
                    self.main_gui_callback("processing_cancelled", {})
                except Exception:
                    pass
    
    def _on_processing_complete(self, result: Dict[str, Any]):
        """
        Handle processing completion on main thread.
        
        Args:
            result: Processing result dictionary
        """
        self.is_processing = False
        self.chat_interface.set_processing_state(False)
        
        # Close progress window
        if self.progress_window and self.progress_window.winfo_exists():
            self.progress_window.destroy()
        
        # Show results
        if result['success']:
            self._show_success_dialog(result)
        else:
            self._show_error_dialog(result)
        
        # Notify main GUI
        if self.main_gui_callback:
            try:
                self.main_gui_callback("processing_complete", result)
            except Exception:
                pass
    
    def _show_success_dialog(self, result: Dict[str, Any]):
        """
        Show success dialog with processing results.
        
        Args:
            result: Processing result dictionary
        """
        flashcard_count = result.get('flashcard_count', 0)
        segment_count = result.get('segment_count', 0)
        processing_time = result.get('processing_time', 0)
        
        message = (
            f"Text processed successfully!\n\n"
            f"Generated: {flashcard_count} flashcards\n"
            f"Text segments: {segment_count}\n"
            f"Processing time: {processing_time:.1f} seconds\n\n"
            f"Flashcards have been imported to Anki."
        )
        
        messagebox.showinfo("Processing Complete", message)
        
        # Ask if user wants to clear the text
        if messagebox.askyesno("Clear Text", "Would you like to clear the text area for new input?"):
            self.chat_interface.clear_text()
    
    def _show_error_dialog(self, result: Dict[str, Any]):
        """
        Show error dialog with failure details.
        
        Args:
            result: Processing result dictionary
        """
        error_msg = result.get('error', 'Unknown error occurred')
        
        message = (
            f"Processing failed:\n\n"
            f"{error_msg}\n\n"
            f"Please check your input and try again."
        )
        
        messagebox.showerror("Processing Failed", message)
    
    def get_chat_interface(self) -> ChatInterface:
        """
        Get the chat interface widget.
        
        Returns:
            ChatInterface instance
        """
        return self.chat_interface
    
    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """
        Get the last processing result.
        
        Returns:
            Last processing result or None
        """
        return self.last_result
    
    def is_processing_active(self) -> bool:
        """
        Check if processing is currently active.
        
        Returns:
            True if processing is in progress
        """
        return self.is_processing
    
    def pack(self, **kwargs):
        """Pack the chat interface widget."""
        self.chat_interface.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the chat interface widget."""
        self.chat_interface.grid(**kwargs)
    
    def place(self, **kwargs):
        """Place the chat interface widget."""
        self.chat_interface.place(**kwargs)


# Demo application
if __name__ == "__main__":
    def demo_callback(event_type: str, data: Dict[str, Any]):
        print(f"Main GUI Event: {event_type} - {data}")
    
    # Create demo window
    root = tk.Tk()
    root.title("Chat Interface Controller Demo")
    root.geometry("1000x800")
    
    # Create controller
    controller = ChatInterfaceController(root, demo_callback)
    controller.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Add demo content
    demo_frame = ttk.Frame(root)
    demo_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
    
    ttk.Label(
        demo_frame,
        text="Demo: Enter text above and click 'Process Text' to test the workflow",
        font=("TkDefaultFont", 10, "italic")
    ).pack()
    
    root.mainloop()