"""Configuration management"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from models.data_models import Configuration, Selector
from constants.selectors import ElementTags


class ConfigManager:
    """Handle all configuration file operations"""
    
    def __init__(self, config_path: str = "custom_patterns.json"):
        self.config_path = Path(__file__).parent.parent / config_path
        self.configs: List[Configuration] = []
        self.selectors_pool = {
            'roles': [],
            'selectors': [],
            'tags': ElementTags.get_defaults()
        }
        self.load_configs()
        
    def load_configs(self) -> List[Configuration]:
        """Load configurations from file"""
        self.configs = []
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        if isinstance(data, list):
                            self.configs = [Configuration.from_dict(item) for item in data]
                        else:
                            self.configs = [Configuration.from_dict(data)]
            self.extract_selectors()
        except Exception as e:
            print(f"Error loading configs: {e}")
            self.configs = []
        return self.configs
    
    def load_scrape_configs(self) -> Dict[str, Any]:
        """Load scrape configurations from config.json"""
        filepath = Path(__file__).parent.parent / "config.json"
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        return data if isinstance(data, dict) else {}
            return {}
        except Exception as e:
            print(f"Error loading scrape configs: {e}")
            return {}
    
    def save_config(self, config: Configuration, is_update: bool = False) -> bool:
        """Save configuration to file"""
        try:
            # Load existing data
            existing_data = []
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        existing_data = json.loads(content)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
            
            config_dict = config.to_dict()
            config_name = config.name
            
            if is_update:
                # Update existing
                replaced = False
                for i, c in enumerate(existing_data):
                    if c.get('name') == config_name:
                        existing_data[i] = config_dict
                        replaced = True
                        break
                if not replaced:
                    # Name changed - remove old
                    existing_data = [c for c in existing_data if c.get('name') != config_name]
                    existing_data.append(config_dict)
            else:
                # Add new
                existing_data.append(config_dict)
            
            # Save to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            # Reload configs
            self.load_configs()
            return True
            
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def save_scrape_config(self, profile_key: str, scraper_selectors: List[Selector], 
                           main_container_index: Optional[int] = None) -> bool:
        """Save scrape configuration to config.json"""
        filepath = Path(__file__).parent.parent / "config.json"
        try:
            data = {}
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        loaded = json.loads(content)
                        data = loaded if isinstance(loaded, dict) else {}
            
            # Build scrape entry
            scrape_entry = {
                "custom_scraper_selectors": [s.to_dict() for s in scraper_selectors]
            }
            if main_container_index is not None:
                scrape_entry["main_container_index"] = main_container_index
            
            data[profile_key] = scrape_entry
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error saving scrape config: {e}")
            return False
    
    def load_scrape_profile(self, profile_key: str) -> tuple:
        """Load scraper selectors and index for a profile"""
        data = self.load_scrape_configs()
        profile = data.get(profile_key, {})
        
        selectors = [Selector.from_dict(s) for s in profile.get('custom_scraper_selectors', [])]
        idx = profile.get('main_container_index')
        
        # Handle both list and single integer formats
        if isinstance(idx, list):
            main_idx = idx[0] if idx else None
        else:
            main_idx = idx
            
        return selectors, main_idx
    
    def delete_config(self, name: str) -> bool:
        """Delete configuration by name"""
        try:
            self.configs = [c for c in self.configs if c.name != name]
            # Save to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump([c.to_dict() for c in self.configs], f, indent=2, ensure_ascii=False)
            self.extract_selectors()
            return True
        except Exception as e:
            print(f"Error deleting config: {e}")
            return False
    
    def extract_selectors(self):
        """Extract all unique selector roles and values from existing configs"""
        
        roles = set()
        selectors = set()
        tags = set(self.selectors_pool.get("tags", []))

        # Process custom configurations (from custom_patterns.json)
        for config in self.configs:
            # Custom selectors
            if hasattr(config, "custom_selectors") and config.custom_selectors:
                for s in config.custom_selectors:
                    role = getattr(s, "role", None)
                    value = getattr(s, "value", None)
                    tag = getattr(s, "tag", None)

                    if role:
                        roles.add(role)
                    if value:
                        selectors.add(value)
                    if tag:
                        tags.add(tag)

        # Process scrape configurations (from config.json)
        scrape_configs = self.load_scrape_configs()
        for profile_key, profile_data in scrape_configs.items():
            # Look for scraper selectors using the actual key name from config.json
            scraper_selectors = profile_data.get('custom_Scraper_selectors', [])
            for s in scraper_selectors:
                # s is already a dict from JSON, not a Selector object
                role = s.get('role')
                value = s.get('value')
                tag = s.get('tag')
                
                if role:
                    roles.add(role)
                if value:
                    selectors.add(value)
                if tag:
                    tags.add(tag)
        
        # Update the pool
        self.selectors_pool['roles'] = sorted(list(roles))
        self.selectors_pool['selectors'] = sorted(list(selectors))
        self.selectors_pool['tags'] = sorted(list(tags))
                        
    def get_config_names(self) -> List[str]:
        """Get list of configuration names"""
        return [c.name for c in self.configs]
    
    def get_config_urls(self) -> List[str]:
        """Get list of unique URLs"""
        return list(set(c.base_url for c in self.configs))
    
    def find_config(self, name: str) -> Optional[Configuration]:
        """Find configuration by name"""
        for config in self.configs:
            if config.name == name:
                return config
        return None
    
    def toggle_config_status(self, name: str) -> Optional[bool]:
        """Toggle active status of configuration"""
        config = self.find_config(name)
        if config:
            config.active = not config.active
            config.update_metadata()
            self.save_config(config, is_update=True)
            return config.active
        return None