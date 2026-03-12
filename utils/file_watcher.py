"""File watching utilities"""
from pathlib import Path
from typing import Optional
from .helpers import file_md5


class FileWatcher:
    """Watch JSON files for external changes"""
    
    def __init__(self, app):
        self.app = app
        self.custom_patterns_path = Path(__file__).parent.parent / "custom_patterns.json"
        self.config_json_path = Path(__file__).parent.parent / "config.json"
        self.last_custom_hash = file_md5(self.custom_patterns_path)
        self.last_config_hash = file_md5(self.config_json_path)
        
    def start_watching(self):
        """Start the file watching loop"""
        self._watch_files()
        
    def _watch_files(self):
        """Poll both JSON files every second"""
        new_custom = file_md5(self.custom_patterns_path)
        new_config = file_md5(self.config_json_path)
        
        if new_custom != self.last_custom_hash:
            self.last_custom_hash = new_custom
            self._on_custom_patterns_changed()
            
        if new_config != self.last_config_hash:
            self.last_config_hash = new_config
            self._on_config_json_changed()
            
        self.app.root.after(1000, self._watch_files)
        
    def _on_custom_patterns_changed(self):
        """Handle custom_patterns.json changes"""
        self.app.config_manager.load_configs()
        
        # Update view tab
        if 'view' in self.app.tabs:
            self.app.tabs['view'].load_configs_into_tree()
            
        # Update automation tab status
        if 'automation' in self.app.tabs:
            self.app.tabs['automation'].refresh_config_status()
            
        # Update config tab comboboxes
        if 'config' in self.app.tabs:
            self.app.tabs['config'].refresh_combos()
            
    def _on_config_json_changed(self):
        """Handle config.json changes"""
        # Update automation tab scrape status
        if 'automation' in self.app.tabs:
            self.app.tabs['automation'].refresh_scrape_status()
            
        # Update config tab profile combobox
        if 'config' in self.app.tabs:
            self.app.tabs['config'].refresh_profile_combo()
            
    def suppress_once(self):
        """
        Call before writing files to prevent self-change detection
        """
        self.last_custom_hash = file_md5(self.custom_patterns_path)
        self.last_config_hash = file_md5(self.config_json_path)