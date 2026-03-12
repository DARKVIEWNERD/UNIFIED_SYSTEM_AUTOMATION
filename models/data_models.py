"""Data models using dataclasses"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Selector:
    """Selector data model"""
    role: str
    tag: str
    type: str
    value: str
    notes: Optional[str] = None
    param: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = {
            "role": self.role,
            "tag": self.tag,
            "type": self.type,
            "value": self.value
        }
        if self.notes:
            data["notes"] = self.notes
        if self.param:
            data["param"] = self.param
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Selector':
        """Create from dictionary"""
        return cls(
            role=data.get('role', ''),
            tag=data.get('tag', ''),
            type=data.get('type', ''),
            value=data.get('value', ''),
            notes=data.get('notes'),
            param=data.get('param')
        )


@dataclass
class Configuration:
    """Configuration data model"""
    name: str
    base_url: str
    active: bool = True
    version: str = "1.0"
    description: str = ""
    custom_selectors: List[Selector] = field(default_factory=list)
    scraper_selectors: List[Selector] = field(default_factory=list)
    main_container_index: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize metadata if empty"""
        if not self.metadata:
            self.metadata = {
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_selectors": len(self.custom_selectors),
                "total_scraper_selectors": len(self.scraper_selectors)
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "active": self.active,
            "version": self.version,
            "description": self.description,
            "custom_selectors": [s.to_dict() for s in self.custom_selectors],
            "scraper_selectors": [s.to_dict() for s in self.scraper_selectors],
            "main_container_index": self.main_container_index,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Configuration':
        """Create from dictionary"""
        idx = data.get('main_container_index')
        # Handle both list and single integer formats
        if isinstance(idx, list):
            main_idx = idx[0] if idx else None
        else:
            main_idx = idx
            
        return cls(
            name=data.get('name', ''),
            base_url=data.get('base_url', ''),
            active=data.get('active', True),
            version=data.get('version', '1.0'),
            description=data.get('description', ''),
            custom_selectors=[Selector.from_dict(s) for s in data.get('custom_selectors', [])],
            scraper_selectors=[Selector.from_dict(s) for s in data.get('scraper_selectors', [])],
            main_container_index=main_idx,
            metadata=data.get('metadata', {})
        )
    
    def update_metadata(self):
        """Update metadata counts"""
        self.metadata['total_selectors'] = len(self.custom_selectors)
        self.metadata['total_scraper_selectors'] = len(self.scraper_selectors)
        self.metadata['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")