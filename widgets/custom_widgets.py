"""Custom reusable widgets"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Any, List, Callable


class LabeledEntry(ttk.Frame):
    """Entry with a label"""
    
    def __init__(self, parent, label: str, **kwargs):
        super().__init__(parent)
        self.label = ttk.Label(self, text=label)
        self.label.pack(side='left', padx=(0, 5))
        
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, **kwargs)
        self.entry.pack(side='left', fill='x', expand=True)
        
    def get(self) -> str:
        """Get entry value"""
        return self.var.get()
        
    def set(self, value: str):
        """Set entry value"""
        self.var.set(value)
        

class LabeledCombobox(ttk.Frame):
    """Combobox with a label"""
    
    def __init__(self, parent, label: str, values: List[str] = None, **kwargs):
        super().__init__(parent)
        self.label = ttk.Label(self, text=label)
        self.label.pack(side='left', padx=(0, 5))
        
        self.var = tk.StringVar()
        self.combo = ttk.Combobox(self, textvariable=self.var, values=values or [], **kwargs)
        self.combo.pack(side='left', fill='x', expand=True)
        
    def get(self) -> str:
        """Get selected value"""
        return self.var.get()
        
    def set(self, value: str):
        """Set selected value"""
        self.var.set(value)
        
    def set_values(self, values: List[str]):
        """Set combobox values"""
        self.combo['values'] = values
        

class ScrollableFrame(ttk.Frame):
    """A scrollable frame"""
    
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Create scrollable frame
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Add frame to canvas
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        self.bind_mousewheel()
        
    def bind_mousewheel(self):
        """Bind mousewheel for scrolling"""
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
    def unbind_mousewheel(self):
        """Unbind mousewheel"""
        self.canvas.unbind_all("<MouseWheel>")
        

class StatusBar(ttk.Frame):
    """Status bar for bottom of window"""
    
    def __init__(self, parent):
        super().__init__(parent, relief='sunken', padding=3)
        
        self.label = ttk.Label(self, text="Ready", anchor='w')
        self.label.pack(side='left', fill='x', expand=True)
        
    def set_text(self, text: str, color: str = 'black'):
        """Set status text"""
        self.label.config(text=text, foreground=color)
        
    def clear(self):
        """Clear status"""
        self.label.config(text="")