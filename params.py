# warna HEX for styling
from typing import TypedDict

class ColorsDict(TypedDict):
    DARKER_BLUE: str
    DARK_BLUE: str
    LIGHTER_BLUE: str
    LIGHT_BLUE: str
    DARKER_GRAY: str
    GRAY: str
    DARK_RED: str
    BLUE: str
    ORANGE: str
    GREEN: str
    RED: str
    PURPLE: str
    # ...add other colors

COLORS:ColorsDict = {
    'DARKER_BLUE': "#1a1a2e",
    'DARK_BLUE': "#16213e",
    'LIGHTER_BLUE': '#00d4ff',
    'LIGHT_BLUE': '#3a4563',
    'DARKER_GRAY': '#555555',
    'GRAY' : "#aaaaaa",
    'DARK_RED' : "#8b0000",
    "BLUE": "#3498db",      # Blue
    "ORANGE": "#f39c12",    # Orange
    "GREEN": "#2ecc71",      # Green
    "RED": "#e74c3c",       # Red
    "PURPLE": "#9b59b6"
}

class StatusIndicator (TypedDict):
    IDLE: str      
    MOVING: str    
    DONE: str      
    ERROR: str    
    HOMED: str     

INDICATOR_COLOR:StatusIndicator = {
    "IDLE": COLORS["BLUE"],      # Blue
    "MOVING": COLORS['ORANGE'],    # Orange
    "DONE": COLORS["GREEN"],     # Green
    "ERROR": COLORS['RED'],     # Red
    "HOMED": COLORS["LIGHT_BLUE"],     # Blue
}