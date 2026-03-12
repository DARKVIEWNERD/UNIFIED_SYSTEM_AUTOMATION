"""Validation utilities"""
import re
from urllib.parse import urlparse
from typing import Optional, Dict, Any


class Validator:
    """Validation methods"""
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        if not url:
            return False
            
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
            
    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL by adding scheme if needed"""
        url = url.strip()
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url
        
    @staticmethod
    def validate_selector(selector: Dict[str, Any]) -> bool:
        """Validate selector data"""
        required = ['role', 'tag', 'type', 'value']
        return all(selector.get(field) for field in required)
        
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
        
    @staticmethod
    def validate_non_empty(value: Optional[str]) -> bool:
        """Check if value is non-empty after stripping"""
        return bool(value and value.strip())