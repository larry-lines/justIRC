"""
Configuration Manager for JustIRC GUI Client
Handles loading and saving user preferences
"""

import json
import os
from typing import Dict, Any


class ConfigManager:
    """Manages client configuration"""
    
    DEFAULT_CONFIG = {
        "theme": "dark",
        "colors": {
            "dark": {
                "bg": "#1e1e1e",
                "fg": "#d4d4d4",
                "chat_bg": "#252526",
                "chat_fg": "#d4d4d4",
                "input_bg": "#3c3c3c",
                "input_fg": "#ffffff",
                "accent": "#007acc",
                "info": "#9cdcfe",
                "error": "#f44747",
                "success": "#6a9955",
                "pm": "#c586c0",
                "channel": "#ce9178",
                "system": "#808080",
                "action": "#dcdcaa",
                "highlight": "#264f78",
                "border": "#454545"
            },
            "light": {
                "bg": "#f3f3f3",
                "fg": "#333333",
                "chat_bg": "#ffffff",
                "chat_fg": "#333333",
                "input_bg": "#ffffff",
                "input_fg": "#000000",
                "accent": "#007acc",
                "info": "#0000ff",
                "error": "#cd3131",
                "success": "#008000",
                "pm": "#982d9d",
                "channel": "#ce9178",
                "system": "#757575",
                "action": "#795548",
                "highlight": "#e6ecf5",
                "border": "#e5e5e5"
            },
            "classic": {
                "bg": "#c0c0c0",
                "fg": "#000000",
                "chat_bg": "#ffffff",
                "chat_fg": "#000000",
                "input_bg": "#ffffff",
                "input_fg": "#000000",
                "accent": "#000080",
                "info": "#0000ff",
                "error": "#ff0000",
                "success": "#008000",
                "pm": "#ff00ff",
                "channel": "#ff8c00",
                "system": "#808080",
                "action": "#8b4513",
                "highlight": "#ffff00",
                "border": "#808080"
            },
            "cyber": {
                "bg": "#0b1015",
                "fg": "#e3f2fd",
                "chat_bg": "#10161d",
                "chat_fg": "#e3f2fd",
                "input_bg": "#1c2530",
                "input_fg": "#ffffff",
                "accent": "#2979ff",
                "info": "#40c4ff",
                "error": "#ff5252",
                "success": "#00e676",
                "pm": "#b388ff",
                "channel": "#69f0ae",
                "system": "#78909c",
                "action": "#64ffda",
                "highlight": "#1a237e",
                "border": "#2979ff",
                "scrollbar_bg": "#1c2530",
                "scrollbar_fg": "#2979ff"
            },
            "custom": {
                "bg": "#2b2b2b",
                "fg": "#ffffff",
                "chat_bg": "#1e1e1e",
                "chat_fg": "#ffffff",
                "input_bg": "#3c3c3c",
                "input_fg": "#ffffff",
                "accent": "#0078d4",
                "info": "#4ec9b0",
                "error": "#f48771",
                "success": "#4ec9b0",
                "pm": "#c586c0",
                "channel": "#dcdcaa",
                "system": "#808080",
                "action": "#ce9178",
                "highlight": "#264f78",
                "border": "#454545",
                "scrollbar_bg": "#3c3c3c",
                "scrollbar_fg": "#808080"
            }
        },
        "font": {
            "family": "Consolas",
            "size": 10,
            "chat_size": 10
        },
        "ui": {
            "show_timestamps": True,
            "show_join_leave": True,
            "sound_notifications": False,
            "compact_mode": False
        },
        "server": {
            "last_server": "localhost",
            "last_port": 6667,
            "last_nickname": ""
        },
        "saved_channels": {}
    }
    
    def __init__(self, config_path: str = "justirc_config.json"):
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return self._merge_configs(self.DEFAULT_CONFIG.copy(), loaded)
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _merge_configs(self, default: dict, loaded: dict) -> dict:
        """Recursively merge loaded config with defaults"""
        for key, value in loaded.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                default[key] = self._merge_configs(default[key], value)
            else:
                default[key] = value
        return default
    
    def get(self, *keys, default=None):
        """Get a config value by path"""
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, *keys, value):
        """Set a config value by path"""
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        self.save_config()
    
    def get_nick_color(self, nickname: str) -> str:
        """Generate a consistent color for a nickname based on hash"""
        import hashlib
        
        # List of readable colors for dark/light themes
        # We'll select based on HSL to ensure visibility or just a curated list
        colors = [
            "#FF7F50", "#20B2AA", "#9370DB", "#3CB371", "#1E90FF",
            "#CD5C5C", "#DA70D6", "#00FA9A", "#4169E1", "#FF69B4",
            "#87CEEB", "#DDA0DD", "#F08080", "#7B68EE", "#00CED1",
            "#FF8C00", "#6A5ACD", "#40E0D0", "#C71585", "#32CD32"
        ]
        
        # Simple hash to pick index
        hash_val = int(hashlib.sha256(nickname.encode()).hexdigest(), 16)
        return colors[hash_val % len(colors)]

    def get_role_symbol(self, is_owner: bool = False, is_op: bool = False, is_mod: bool = False) -> str:
        """Get symbol for user role"""
        if is_owner:
            return "👑"  # Crown for owner
        elif is_op:
            return "⭐"  # Star for operator
        elif is_mod:
            return "🛡️"  # Shield for mod
        else:
            return "👤"  # Person for regular user

    def get_theme_colors(self):
        """Get colors for current theme"""
        theme = self.config.get("theme", "dark")
        return self.config["colors"].get(theme, self.config["colors"]["dark"])
