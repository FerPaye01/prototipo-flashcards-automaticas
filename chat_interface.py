"""
Chat Interface Component for Flashcards UI Enhancement

This module provides the ChatInterface class that creates a text area component
for direct text input with scrolling, validation, and character count display.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional, Callable
import re


class ChatInterface(ttk.Frame):
    """
    A chat-like interface component for direct text input.
    
    Provides:
    - Large text area with scroll functionality
    - Character/word count display
    - Input validation
    - Content preview
    - Placeholder text support
    """
    
    def __init__(self, parent, validation_callback: Optional[Callable[[str], bool]] = None):
        """
        Initialize the ChatInterface component.
        
        Args:
            parent: Parent tkinter widget
            validation_callback: Optional function to validate input content
        """
        super().__init__(parent)
        self.validation_callback = validation_callback
        
        # Configuration (will be updated from config manager)
        self.min_chars = 10  # Minimum characters for valid input
        self.max_chars = 50000  # Maximum characters allowed
        self.min_unique_characters = 5  # Minimum unique characters
        self.require_alphabetic_content = True  # Require alphabetic content
        self.max_repetition_ratio = 0.8  # Maximum repetition ratio
        self.placeholder_text = "Enter your study material here...\n\nYou can:\n• Paste text from documents\n• Type directly\n• Include multiple paragraphs\n\nClick 'Process Text' when ready to generate flashcards."
        
        # State variables
        self.is_placeholder_active = True
        self.last_char_count = 0
        self.last_word_count = 0
        
        # Widget references
        self.text_area = None
        self.char_count_label = None
        self.word_count_label = None
        self.validation_label = None
        self.clear_button = None
        self.process_button = None
        
        self._create_interface()
        self._setup_placeholder()
        self._update_counts()
    
    def _create_interface(self):
        """Create the main interface layout."""
        # Configure main frame
        self.configure(padding=10)
        
        # Header frame with title and counts
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        title_label = ttk.Label(
            header_frame,
            text="Direct Text Input",
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(side=tk.LEFT)
        
        # Count display frame
        count_frame = ttk.Frame(header_frame)
        count_frame.pack(side=tk.RIGHT)
        
        self.char_count_label = ttk.Label(
            count_frame,
            text="Characters: 0",
            font=("TkDefaultFont", 9),
            foreground="#666666"
        )
        self.char_count_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.word_count_label = ttk.Label(
            count_frame,
            text="Words: 0",
            font=("TkDefaultFont", 9),
            foreground="#666666"
        )
        self.word_count_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Text area frame
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create scrolled text widget
        self.text_area = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            width=80,
            height=20,
            font=("TkDefaultFont", 10),
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=10
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # Bind events for real-time updates
        self.text_area.bind('<KeyRelease>', self._on_text_changed)
        self.text_area.bind('<Button-1>', self._on_text_clicked)
        self.text_area.bind('<FocusIn>', self._on_focus_in)
        self.text_area.bind('<FocusOut>', self._on_focus_out)
        
        # Validation and status frame
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.validation_label = ttk.Label(
            status_frame,
            text="",
            font=("TkDefaultFont", 9),
            foreground="#666666"
        )
        self.validation_label.pack(side=tk.LEFT)
        
        # Button frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X)
        
        self.clear_button = ttk.Button(
            button_frame,
            text="Clear Text",
            command=self.clear_text
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.process_button = ttk.Button(
            button_frame,
            text="Process Text",
            command=self._on_process_clicked,
            state="disabled"
        )
        self.process_button.pack(side=tk.RIGHT)
    
    def _setup_placeholder(self):
        """Setup placeholder text in the text area."""
        self.text_area.insert("1.0", self.placeholder_text)
        self.text_area.configure(foreground="#999999")
        self.is_placeholder_active = True
    
    def _on_text_changed(self, event=None):
        """Handle text change events."""
        # Update counts and validation
        self._update_counts()
        self._update_validation()
        
        # Check if placeholder should be removed
        if self.is_placeholder_active:
            current_text = self.text_area.get("1.0", tk.END).strip()
            if current_text != self.placeholder_text.strip():
                self._remove_placeholder()
    
    def _on_text_clicked(self, event=None):
        """Handle text area click events."""
        if self.is_placeholder_active:
            self._remove_placeholder()
    
    def _on_focus_in(self, event=None):
        """Handle focus in events."""
        if self.is_placeholder_active:
            # Don't remove placeholder immediately, wait for actual input
            pass
    
    def _on_focus_out(self, event=None):
        """Handle focus out events."""
        current_text = self.get_text().strip()
        if not current_text and not self.is_placeholder_active:
            self._setup_placeholder()
    
    def _remove_placeholder(self):
        """Remove placeholder text and setup for user input."""
        if self.is_placeholder_active:
            self.text_area.delete("1.0", tk.END)
            self.text_area.configure(foreground="#000000")
            self.is_placeholder_active = False
            self._update_counts()
            self._update_validation()
    
    def _update_counts(self):
        """Update character and word counts."""
        if self.is_placeholder_active:
            char_count = 0
            word_count = 0
        else:
            text = self.get_text()
            char_count = len(text)
            word_count = len(text.split()) if text.strip() else 0
        
        # Update labels
        self.char_count_label.configure(text=f"Characters: {char_count}")
        self.word_count_label.configure(text=f"Words: {word_count}")
        
        # Store counts
        self.last_char_count = char_count
        self.last_word_count = word_count
    
    def _update_validation(self):
        """Update validation status and button states."""
        is_valid = self.validate_input()
        
        if self.is_placeholder_active or self.last_char_count == 0:
            self.validation_label.configure(
                text="Enter text to begin",
                foreground="#666666"
            )
            self.process_button.configure(state="disabled")
        elif self.last_char_count < self.min_chars:
            self.validation_label.configure(
                text=f"Minimum {self.min_chars} characters required",
                foreground="#d13438"
            )
            self.process_button.configure(state="disabled")
        elif self.last_char_count > self.max_chars:
            self.validation_label.configure(
                text=f"Maximum {self.max_chars} characters exceeded",
                foreground="#d13438"
            )
            self.process_button.configure(state="disabled")
        elif not is_valid:
            self.validation_label.configure(
                text="Content validation failed",
                foreground="#d13438"
            )
            self.process_button.configure(state="disabled")
        else:
            self.validation_label.configure(
                text="Ready to process",
                foreground="#107c10"
            )
            self.process_button.configure(state="normal")
    
    def _on_process_clicked(self):
        """Handle process button click."""
        if self.validate_input():
            # This will be connected to the main processing workflow
            text = self.get_text()
            print(f"Processing text: {len(text)} characters, {len(text.split())} words")
            # TODO: Connect to actual processing pipeline
    
    def get_text(self) -> str:
        """
        Get the current text content.
        
        Returns:
            Current text content (empty string if placeholder is active)
        """
        if self.is_placeholder_active:
            return ""
        
        text = self.text_area.get("1.0", tk.END)
        # Remove the trailing newline that tkinter adds
        return text.rstrip('\n')
    
    def set_text(self, text: str):
        """
        Set the text content.
        
        Args:
            text: Text to set
        """
        self._remove_placeholder()
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", text)
        self._update_counts()
        self._update_validation()
    
    def clear_text(self):
        """Clear all text and restore placeholder."""
        self.text_area.delete("1.0", tk.END)
        self._setup_placeholder()
        self._update_counts()
        self._update_validation()
    
    def set_placeholder(self, text: str):
        """
        Set custom placeholder text.
        
        Args:
            text: Placeholder text to display
        """
        self.placeholder_text = text
        if self.is_placeholder_active:
            self.text_area.delete("1.0", tk.END)
            self._setup_placeholder()
    
    def validate_input(self) -> bool:
        """
        Validate the current input using configuration-based validation.
        
        Returns:
            True if input is valid
        """
        if self.is_placeholder_active:
            return False
        
        text = self.get_text().strip()
        
        # Basic validation
        if not text:
            return False
        
        if len(text) < self.min_chars:
            return False
        
        if len(text) > self.max_chars:
            return False
        
        # Advanced validation based on configuration
        if not self._validate_content_quality(text):
            return False
        
        # Custom validation callback
        if self.validation_callback:
            try:
                return self.validation_callback(text)
            except Exception:
                return False
        
        return True
    
    def _validate_content_quality(self, text: str) -> bool:
        """
        Validate content quality based on configuration settings.
        
        Args:
            text: Text to validate
            
        Returns:
            True if content meets quality requirements
        """
        # Check unique characters
        unique_chars = len(set(text.lower().replace(' ', '')))
        if unique_chars < self.min_unique_characters:
            return False
        
        # Check for alphabetic content if required
        if self.require_alphabetic_content:
            if not any(c.isalpha() for c in text):
                return False
        
        # Check repetition ratio
        if self._calculate_repetition_ratio(text) > self.max_repetition_ratio:
            return False
        
        return True
    
    def _calculate_repetition_ratio(self, text: str) -> float:
        """
        Calculate the repetition ratio of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Repetition ratio (0.0 to 1.0)
        """
        if not text:
            return 0.0
        
        # Split into words and count occurrences
        words = text.lower().split()
        if not words:
            return 0.0
        
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Calculate repetition ratio
        total_words = len(words)
        unique_words = len(word_counts)
        
        if unique_words == 0:
            return 1.0
        
        # Ratio of repeated words to total words
        repeated_words = sum(count - 1 for count in word_counts.values() if count > 1)
        return repeated_words / total_words if total_words > 0 else 0.0
    
    def update_validation_settings(self, min_chars: int = None, max_chars: int = None, 
                                 min_unique_chars: int = None, require_alphabetic: bool = None,
                                 max_repetition_ratio: float = None):
        """
        Update validation settings.
        
        Args:
            min_chars: Minimum character count
            max_chars: Maximum character count
            min_unique_chars: Minimum unique characters
            require_alphabetic: Whether to require alphabetic content
            max_repetition_ratio: Maximum repetition ratio
        """
        if min_chars is not None:
            self.min_chars = min_chars
        if max_chars is not None:
            self.max_chars = max_chars
        if min_unique_chars is not None:
            self.min_unique_characters = min_unique_chars
        if require_alphabetic is not None:
            self.require_alphabetic_content = require_alphabetic
        if max_repetition_ratio is not None:
            self.max_repetition_ratio = max_repetition_ratio
        
        # Update validation display
        self._update_validation()
    
    def get_char_count(self) -> int:
        """Get current character count."""
        return self.last_char_count
    
    def get_word_count(self) -> int:
        """Get current word count."""
        return self.last_word_count
    
    def set_processing_state(self, is_processing: bool):
        """
        Set processing state to disable/enable controls.
        
        Args:
            is_processing: True if processing is in progress
        """
        state = "disabled" if is_processing else "normal"
        self.text_area.configure(state=state)
        self.clear_button.configure(state=state)
        
        if is_processing:
            self.process_button.configure(state="disabled", text="Processing...")
        else:
            self._update_validation()  # This will set correct button state
            self.process_button.configure(text="Process Text")


# Demo/Test function
def _demo_validation(text: str) -> bool:
    """Demo validation function."""
    # Example: reject text that's all uppercase
    return not text.isupper()


if __name__ == "__main__":
    # Demo application
    root = tk.Tk()
    root.title("ChatInterface Demo")
    root.geometry("900x700")
    
    # Create chat interface
    chat = ChatInterface(root, _demo_validation)
    chat.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Add demo controls
    control_frame = ttk.Frame(root)
    control_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
    
    ttk.Button(
        control_frame,
        text="Set Sample Text",
        command=lambda: chat.set_text("This is sample study material.\n\nIt contains multiple paragraphs and should be long enough to pass validation.")
    ).pack(side=tk.LEFT, padx=(0, 10))
    
    ttk.Button(
        control_frame,
        text="Simulate Processing",
        command=lambda: chat.set_processing_state(True)
    ).pack(side=tk.LEFT, padx=(0, 10))
    
    ttk.Button(
        control_frame,
        text="Stop Processing",
        command=lambda: chat.set_processing_state(False)
    ).pack(side=tk.LEFT)
    
    root.mainloop()