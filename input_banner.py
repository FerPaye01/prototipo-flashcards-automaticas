"""
Input Banner Component for Flashcards UI Enhancement

This module provides the InputBanner class that creates a visual banner
showing all input method options with clear visual hierarchy and selection feedback.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class InputBanner(ttk.Frame):
    """
    A banner component that displays input method options with visual selection states.
    
    Provides three main input methods:
    - PDF with Annotations
    - PDF Full Text  
    - Direct Text Input
    """
    
    # Input mode constants
    MODE_PDF_ANNOTATIONS = "pdf_annotations"
    MODE_PDF_FULLTEXT = "pdf_fulltext"
    MODE_DIRECT_TEXT = "direct_text"
    MODE_ANKI_SYNC = "anki_sync"
    
    def __init__(self, parent, callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the InputBanner component.
        
        Args:
            parent: Parent tkinter widget
            callback: Function to call when input method is selected
        """
        super().__init__(parent)
        self.callback = callback
        self.active_mode = self.MODE_PDF_ANNOTATIONS  # Default mode
        
        # Style configuration
        self.style = ttk.Style()
        self._configure_styles()
        
        # Widget references
        self.mode_buttons = {}
        self.sub_option_frames = {}
        
        self._create_banner_layout()
        self._update_visual_states()
    
    def _configure_styles(self):
        """Configure custom styles for the banner components."""
        # Active button style
        self.style.configure(
            "Active.TButton",
            background="#0078d4",
            foreground="white",
            relief="solid",
            borderwidth=2
        )
        
        # Inactive button style  
        self.style.configure(
            "Inactive.TButton",
            background="#f0f0f0",
            foreground="#333333",
            relief="raised",
            borderwidth=1
        )
        
        # Hover style
        self.style.map(
            "Inactive.TButton",
            background=[("active", "#e1e1e1")],
            relief=[("active", "solid")]
        )
        
        # Banner frame style
        self.style.configure(
            "Banner.TFrame",
            background="#ffffff",
            relief="solid",
            borderwidth=1
        )
    
    def _create_banner_layout(self):
        """Create the main banner layout with input method options."""
        # Configure banner frame
        self.configure(style="Banner.TFrame", padding=10)
        
        # Title label
        title_label = ttk.Label(
            self,
            text="Select Input Method",
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Main buttons container
        buttons_frame = ttk.Frame(self)
        buttons_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Create main input method buttons
        self._create_mode_button(
            buttons_frame,
            self.MODE_PDF_ANNOTATIONS,
            "PDF with Annotations",
            "Extract content from highlighted/annotated text in PDF files"
        )
        
        self._create_mode_button(
            buttons_frame,
            self.MODE_PDF_FULLTEXT,
            "PDF Full Text",
            "Extract all text content from PDF files"
        )
        
        self._create_mode_button(
            buttons_frame,
            self.MODE_DIRECT_TEXT,
            "Direct Text Input",
            "Enter study material directly through text interface"
        )
        
        self._create_mode_button(
            buttons_frame,
            self.MODE_ANKI_SYNC,
            "Anki Sync",
            "Synchronize flashcards to Anki with multiple deck support"
        )
        
        # Sub-options container (for PDF processing modes)
        self.sub_options_frame = ttk.Frame(self)
        self.sub_options_frame.pack(fill=tk.X, pady=(5, 0))
        
        self._create_sub_options()
    
    def _create_mode_button(self, parent, mode: str, text: str, tooltip: str):
        """
        Create a mode selection button with hover effects.
        
        Args:
            parent: Parent widget
            mode: Mode identifier
            text: Button text
            tooltip: Tooltip text for help
        """
        button = ttk.Button(
            parent,
            text=text,
            command=lambda: self._on_mode_selected(mode),
            style="Inactive.TButton"
        )
        button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Store button reference
        self.mode_buttons[mode] = button
        
        # Add tooltip
        self._create_tooltip(button, tooltip)
        
        # Bind hover events for visual feedback
        button.bind("<Enter>", lambda e: self._on_button_hover(mode, True))
        button.bind("<Leave>", lambda e: self._on_button_hover(mode, False))
    
    def _create_sub_options(self):
        """Create sub-option displays for PDF processing modes."""
        # PDF Annotations sub-options
        pdf_ann_frame = ttk.Frame(self.sub_options_frame)
        pdf_ann_label = ttk.Label(
            pdf_ann_frame,
            text="• Extracts only highlighted or annotated content",
            font=("TkDefaultFont", 9),
            foreground="#666666"
        )
        pdf_ann_label.pack(anchor="w")
        
        # PDF Full Text sub-options
        pdf_full_frame = ttk.Frame(self.sub_options_frame)
        pdf_full_label = ttk.Label(
            pdf_full_frame,
            text="• Extracts complete text content from all pages",
            font=("TkDefaultFont", 9),
            foreground="#666666"
        )
        pdf_full_label.pack(anchor="w")
        
        # Direct Text sub-options
        direct_frame = ttk.Frame(self.sub_options_frame)
        direct_label = ttk.Label(
            direct_frame,
            text="• Type or paste content directly into text area",
            font=("TkDefaultFont", 9),
            foreground="#666666"
        )
        direct_label.pack(anchor="w")
        
        # Anki Sync sub-options
        anki_frame = ttk.Frame(self.sub_options_frame)
        anki_label = ttk.Label(
            anki_frame,
            text="• Sync up to 4 decks with different flashcard types (Basic, Multiple Choice, Cloze, Vocabulary)",
            font=("TkDefaultFont", 9),
            foreground="#666666"
        )
        anki_label.pack(anchor="w")
        
        # Store sub-option frames
        self.sub_option_frames[self.MODE_PDF_ANNOTATIONS] = pdf_ann_frame
        self.sub_option_frames[self.MODE_PDF_FULLTEXT] = pdf_full_frame
        self.sub_option_frames[self.MODE_DIRECT_TEXT] = direct_frame
        self.sub_option_frames[self.MODE_ANKI_SYNC] = anki_frame
    
    def _create_tooltip(self, widget, text: str):
        """
        Create a tooltip for the given widget.
        
        Args:
            widget: Widget to attach tooltip to
            text: Tooltip text
        """
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            
            label = ttk.Label(
                tooltip,
                text=text,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                font=("TkDefaultFont", 9)
            )
            label.pack()
            
            # Auto-hide after 3 seconds
            tooltip.after(3000, tooltip.destroy)
        
        def hide_tooltip(event):
            # Tooltip auto-hides, no action needed
            pass
        
        widget.bind("<Button-3>", show_tooltip)  # Right-click to show tooltip
    
    def _on_mode_selected(self, mode: str):
        """
        Handle mode selection.
        
        Args:
            mode: Selected mode identifier
        """
        if mode != self.active_mode:
            self.active_mode = mode
            self._update_visual_states()
            
            # Call callback if provided
            if self.callback:
                self.callback(mode)
    
    def _on_button_hover(self, mode: str, is_entering: bool):
        """
        Handle button hover effects.
        
        Args:
            mode: Button mode
            is_entering: True if mouse entering, False if leaving
        """
        if mode != self.active_mode:  # Don't change active button appearance
            button = self.mode_buttons[mode]
            if is_entering:
                button.configure(style="Inactive.TButton")
                # Additional hover effect could be added here
            else:
                button.configure(style="Inactive.TButton")
    
    def _update_visual_states(self):
        """Update visual states of all buttons and sub-options."""
        # Update button styles
        for mode, button in self.mode_buttons.items():
            if mode == self.active_mode:
                button.configure(style="Active.TButton")
            else:
                button.configure(style="Inactive.TButton")
        
        # Update sub-option visibility
        for mode, frame in self.sub_option_frames.items():
            if mode == self.active_mode:
                frame.pack(fill=tk.X, pady=(5, 0))
            else:
                frame.pack_forget()
    
    def set_active_mode(self, mode: str):
        """
        Programmatically set the active mode.
        
        Args:
            mode: Mode to activate
        """
        if mode in self.mode_buttons:
            self._on_mode_selected(mode)
    
    def get_active_mode(self) -> str:
        """
        Get the currently active mode.
        
        Returns:
            Active mode identifier
        """
        return self.active_mode


# Demo/Test function
def _demo_callback(mode: str):
    """Demo callback function for testing."""
    print(f"Selected mode: {mode}")


if __name__ == "__main__":
    # Demo application
    root = tk.Tk()
    root.title("InputBanner Demo")
    root.geometry("800x300")
    
    banner = InputBanner(root, _demo_callback)
    banner.pack(fill=tk.X, padx=20, pady=20)
    
    # Add some demo content below
    demo_label = ttk.Label(
        root,
        text="This is a demo of the InputBanner component.\nClick buttons to see selection states.",
        justify="center"
    )
    demo_label.pack(pady=20)
    
    root.mainloop()