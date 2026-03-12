"""Selector-related constants"""


class SelectorTypes:
    """Types of selectors"""
    TEXT = 'text'
    BUTTON = 'button'
    LINK = 'link'
    DROPDOWN = 'dropdown'
    CHECKBOX = 'checkbox'
    INPUT = 'input'
    MULTIPLE = 'multiple'
    CONTAINER = 'container'
    
    ALL = [TEXT, BUTTON, LINK, DROPDOWN, CHECKBOX, INPUT, MULTIPLE, CONTAINER]
    
    @classmethod
    def get_display_names(cls):
        """Get display names for combobox"""
        return cls.ALL


class ElementTags:
    """HTML element tags"""
    DEFAULT_TAGS = ['div', 'button', 'input', 'a', 'span', 'select',
                    'form', 'img', 'li', 'h1', 'h2', 'p']
    
    @classmethod
    def get_defaults(cls):
        """Get default tags"""
        return cls.DEFAULT_TAGS.copy()