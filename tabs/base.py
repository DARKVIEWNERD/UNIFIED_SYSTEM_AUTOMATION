"""Base tab class"""
import tkinter as tk
from tkinter import ttk


class Base:
    """Base class for all tabs"""
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.frame = ttk.Frame(parent)
        self.title = "Tab"
        
    def build(self):
        """Build tab UI - to be overridden"""
        raise NotImplementedError
        
    def get_title(self) -> str:
        """Get tab title"""
        return self.title
        
    def create_scrollable_frame(self, parent):
        """Create a scrollable frame"""
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        return canvas, scrollbar, scrollable_frame