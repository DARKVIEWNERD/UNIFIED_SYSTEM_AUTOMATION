"""Logging management"""
import logging
import queue
import sys
from io import StringIO
from typing import Optional
from tkinter import scrolledtext, END
from constants.ui import Colors


class QueueHandler(logging.Handler):
    """Custom logging handler to put records into a queue"""
    
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        
    def emit(self, record):
        self.log_queue.put(self.format(record))


class GUITextIO(StringIO):
    """Custom StringIO to redirect stdout to GUI"""
    
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        
    def write(self, s):
        if s.strip():
            self.queue.put(s)
        super().write(s)


class LogManager:
    """Manage all logging operations"""
    
    def __init__(self):
        self.log_queue = queue.Queue()
        self.stdout_queue = queue.Queue()
        self.log_text: Optional[scrolledtext.ScrolledText] = None
        self.stats = {
            'success': 0,
            'fail': 0,
            'files': 0,
            'entries': 0
        }
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging handlers"""
        # Setup queue handler
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        queue_handler.setFormatter(formatter)
        
        # Add to root logger
        root_logger = logging.getLogger()
        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        root_logger.addHandler(queue_handler)
        root_logger.setLevel(logging.INFO)
        
        # Redirect stdout
        sys.stdout = GUITextIO(self.stdout_queue)
        
    def attach_log_widget(self, log_text: scrolledtext.ScrolledText):
        """Attach log display widget"""
        self.log_text = log_text
        self._configure_log_tags()
        
    def _configure_log_tags(self):
        """Configure text tags for log coloring"""
        if self.log_text:
            self.log_text.tag_config('ERROR', foreground=Colors.ERROR)
            self.log_text.tag_config('WARNING', foreground=Colors.WARNING)
            self.log_text.tag_config('INFO', foreground=Colors.INFO)
            self.log_text.tag_config('DEBUG', foreground=Colors.DEBUG)
            self.log_text.tag_config('SUCCESS', foreground=Colors.SUCCESS)
            self.log_text.tag_config('highlight', background='yellow', foreground='black')
            
    def process_log_entry(self, record: str) -> str:
        """Process a log entry and return tag"""
        if 'ERROR' in record:
            tag = 'ERROR'
            self.stats['fail'] += 1
        elif 'WARNING' in record:
            tag = 'WARNING'
        elif 'SUCCESS' in record or '✅' in record:
            tag = 'SUCCESS'
            self.stats['success'] += 1
        elif 'INFO' in record:
            tag = 'INFO'
        else:
            tag = 'DEBUG'
            
        # Check for file creation
        if 'MHTML' in record and ('saved' in record.lower() or 'created' in record.lower()):
            self.stats['files'] += 1
            
        self.stats['entries'] += 1
        return tag
        
    def update_display(self) -> bool:
        """Update log display from queue"""
        if not self.log_text:
            return False
            
        updated = False
        
        # Process log queue
        try:
            while True:
                record = self.log_queue.get_nowait()
                tag = self.process_log_entry(record)
                self.log_text.configure(state='normal')
                self.log_text.insert(END, record + '\n', tag)
                self.log_text.see(END)
                self.log_text.configure(state='disabled')
                updated = True
        except queue.Empty:
            pass
            
        # Process stdout queue
        try:
            while True:
                record = self.stdout_queue.get_nowait()
                self.log_text.config(state='normal') 
                self.log_text.insert(END, record + '\n', 'INFO')
                self.log_text.see(END)
                self.log_text.config(state='disabled')
                updated = True
        except queue.Empty:
            pass
            
        return updated
        
    def clear_logs(self):
        """Clear all logs and reset stats"""
        if self.log_text:
                self.log_text.config(state='normal')      # ← unlock
                self.log_text.delete(1.0, END)
                self.log_text.config(state='disabled')    # ← lock again
        self.stats = {'success': 0, 'fail': 0, 'files': 0, 'entries': 0}
        
    def get_log_content(self) -> str:
        """Get all log content"""
        if self.log_text:
            return self.log_text.get(1.0, END)
        return ""
        
    def filter_logs(self, filter_text: str):
        """Highlight matching log lines"""
        if not self.log_text:
            return
            
        self.log_text.tag_remove('highlight', 1.0, END)
        if filter_text:
            start = 1.0
            while True:
                pos = self.log_text.search(filter_text.lower(), start, END)
                if not pos:
                    break
                end = f"{pos}+{len(filter_text)}c"
                self.log_text.tag_add('highlight', pos, end)
                start = end