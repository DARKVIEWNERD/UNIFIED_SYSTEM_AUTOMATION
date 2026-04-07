"""Selector-related constants"""


class SelectorTypes:
    """Types of selectors"""

 
    
    Custom = ["input","select","dropdown","list","click"]
    Scrape = ["id","class"]

    
    @classmethod
    def get_display_names(cls,mode):

        """Get display names for combobox"""
        if mode=='custom':
            return cls.Custom
        else:
            return cls.Scrape



class ElementTags:
    """HTML element tags"""
    DEFAULT_TAGS = ['div', 'button', 'input', 'a', 'span', 'select',
                    'form', 'img', 'li', 'h1', 'h2', 'p']
    
    @classmethod
    def get_defaults(cls):
        """Get default tags"""
        return cls.DEFAULT_TAGS.copy()