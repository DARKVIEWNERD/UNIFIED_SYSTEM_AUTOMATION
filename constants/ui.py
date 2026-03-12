"""UI-related constants"""


class UIConstants:
    """Window and UI configuration"""
    WINDOW_TITLE = "🤖 Multi-Platform Automation Controller"
    WINDOW_SIZE = "1100x740"
    WINDOW_MIN_SIZE = (1000, 600)
    
    FONTS = {
        'header': ('Arial', 16, 'bold'),
        'subheader': ('Arial', 10),
        'status': ('Arial', 10),
        'button': ('Arial', 10),
        'log': ('Consolas', 9)
    }
    
    PADDING = {
        'small': 3,
        'medium': 5,
        'large': 10
    }


class Colors:
    """Color constants"""
    SUCCESS = '#00ff00'
    ERROR = '#ff5555'
    WARNING = '#ffaa00'
    INFO = '#00ff00'
    DEBUG = '#888888'
    BACKGROUND = '#f8f9fa'
    ACTIVE_GREEN = '#27ae60'
    INACTIVE_RED = '#e74c3c'
    SCRAPE_ORANGE = '#e67e22'


class LogLevel:
    """Log level constants"""
    INFO = "INFO"
    ERROR = "ERROR"
    WARNING = "WARNING"
    SUCCESS = "SUCCESS"
    DEBUG = "DEBUG"
    ALL = "ALL"