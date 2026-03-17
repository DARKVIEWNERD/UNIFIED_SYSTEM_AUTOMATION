#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import logging

from managers.config_manager import ConfigManager
from managers.log_manager import LogManager
from tabs.Automation_Tab import AutomationTab
from tabs.config_tab import ConfigTab
from tabs.view_tab import ViewTab
from constants.ui import UIConstants
from utils.file_watcher import FileWatcher 

class AutomationGUI:
    """Main application window"""
    
    def __init__(self, root):
        self.root = root
        self.root.title(UIConstants.WINDOW_TITLE)
        self.root.geometry(UIConstants.WINDOW_SIZE)
        self.root.minsize(*UIConstants.WINDOW_MIN_SIZE)
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.log_manager = LogManager()
        self.file_watcher = FileWatcher(self)
        
        # State variables
        self.is_running = False
        self.stop_flag = False
        self.start_time = None
        
        # Apply modern style
        self.setup_styles()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Initialize tabs
        self.tabs = {}
        self.init_tabs()
        
        # Start file watcher
        self.file_watcher.start_watching()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_styles(self):
   
        style = ttk.Style()
        style.configure('Header.TLabel', font=UIConstants.FONTS['header'])
        style.configure('SubHeader.TLabel', font=UIConstants.FONTS['subheader'], foreground='gray')
        style.configure('Status.TLabel', font=UIConstants.FONTS['status'])
        style.configure('Success.TButton', font=UIConstants.FONTS['button'])
        style.configure('Danger.TButton', font=UIConstants.FONTS['button'])
        style.configure('Action.TButton', font=UIConstants.FONTS['button'])
        style.configure('Card.TLabelframe', background='#f8f9fa')
        
    def init_tabs(self):
        """Initialize all tabs"""
        tab_classes = {
            'automation': AutomationTab,
            'config': ConfigTab,
            'view': ViewTab
        }
        
        for tab_name, tab_class in tab_classes.items():
            tab = tab_class(self.notebook, self)
            tab.build()
            self.tabs[tab_name] = tab
            self.notebook.add(tab.frame, text=tab.get_title())
            
    def on_closing(self):
        """Handle window close event"""
        if self.is_running:
            from tkinter import messagebox
            if messagebox.askyesno("Exit", "Automation is still running. Stop and exit?"):
                self.tabs['automation'].stop_automation()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """Main entry point"""
    root = tk.Tk()
    app = AutomationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()