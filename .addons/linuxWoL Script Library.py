#!/usr/bin/env python3
import glob
import json
import os
import sys

# Comprehensive Theme & System Configuration Dictionary
GUI_THEME = {
    # Color Palette Variables
    "bg": "#071b2b",
    "bg_alt": "#0a2740",
    "panel": "#0f3353",
    "panel_2": "#153f66",
    "blue": "#1e88e5",
    "blue_dark": "#0d47a1",
    "blue_light": "#cfe8ff",
    "white": "#f2f8ff",
    "black": "#020b13",
    "muted": "#9dc8ff",
    "accent": "#2ba7ff",
    "success": "#1cc88a",
    "warn": "#ffd166",
    "danger": "#ff6b6b",
    "border": "#214e75",
    "hover": "#2563eb",
    "active": "#1d4ed8",
    "shadow": "rgba(0, 0, 0, 0.4)",
    # Typography Variables
    "font_family": "Segoe UI, Helvetica, Arial, sans-serif",
    "font_size_sm": 11,
    "font_size_md": 14,
    "font_size_lg": 18,
    "font_size_xl": 24,
    "font_weight_normal": "400",
    "font_weight_bold": "700",
    # Layout & Dimension Variables
    "window_width": 800,
    "window_height": 600,
    "padding_sm": 8,
    "padding_md": 16,
    "padding_lg": 24,
    "border_radius": 6,
    "button_height": 40,
    # Network & Wake-on-LAN Variables
    "default_mac": "FF:FF:FF:FF:FF:FF",
    "default_ip": "255.255.255.255",
    "default_port": 9,
    "packet_count": 5,
    "socket_timeout": 2.0,
    # System & App State Variables
    "app_title": "Theme & Add-on Manager",
    "app_version": "2.0.0",
    "debug_mode": False,
}


class ThemeInterpreter:
    """Interprets UI configurations, theme definitions, and custom add-ons."""

    def __init__(self, default_theme: dict = None):
        self.themes = {"default": default_theme or GUI_THEME.copy()}
        self.active_theme_name = "default"
        self.addons = []
        self._unpack_variables()

    def _unpack_variables(self) -> None:
        """Exposes all active theme keys directly as instance attributes."""
        active_config = self.get_active_theme()
        for key, value in active_config.items():
            setattr(self, key, value)

    def register_theme(self, name: str, theme_dict: dict) -> None:
        """Registers a UI theme directly from a dictionary."""
        self.themes[name] = theme_dict

    def load_theme_file(self, filepath: str) -> str:
        """Loads a theme add-on from a JSON configuration file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Theme file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        theme_name = data.get("name", os.path.splitext(os.path.basename(filepath))[0])
        colors_and_vars = data.get("variables", data.get("colors", data))
        self.themes[theme_name] = colors_and_vars
        return theme_name

    def load_theme_directory(self, dir_path: str) -> list:
        """Loads all JSON theme add-ons inside a target folder."""
        loaded = []
        if os.path.isdir(dir_path):
            for file in glob.glob(os.path.join(dir_path, "*.json")):
                try:
                    name = self.load_theme_file(file)
                    loaded.append(name)
                except Exception as err:
                    print(f"Failed to load theme {file}: {err}", file=sys.stderr)
        return loaded

    def set_active_theme(self, name: str) -> bool:
        """Switches active theme and updates instance attributes."""
        if name in self.themes:
            self.active_theme_name = name
            self._unpack_variables()
            return True
        return False

    def get_active_theme(self) -> dict:
        """Retrieves active UI theme color and configuration definitions."""
        return self.themes.get(self.active_theme_name, self.themes["default"])

    def get_all_variables(self) -> dict:
        """Returns a consolidated dictionary of all active system & theme variables."""
        return {
            **self.get_active_theme(),
            "active_theme_name": self.active_theme_name,
            "registered_themes": list(self.themes.keys()),
            "registered_addons_count": len(self.addons),
        }

    def register_addon(self, addon_callback) -> None:
        """Registers a custom UI add-on function."""
        if callable(addon_callback):
            self.addons.append(addon_callback)

    def run_addons(self, context: dict = None) -> None:
        """Executes registered UI add-ons passing theme and full context data."""
        ctx = context or {}
        full_vars = self.get_all_variables()
        for addon in self.addons:
            try:
                addon(full_vars, ctx)
            except Exception as err:
                print(f"[Add-on Execution Error]: {err}", file=sys.stderr)


# Entrypoint Demonstration
if __name__ == "__main__":
    interpreter = ThemeInterpreter()
    all_vars = interpreter.get_all_variables()

    print(f"App Title: {interpreter.app_title} (v{interpreter.app_version})")
    print(f"Default MAC: {interpreter.default_mac} | Port: {interpreter.default_port}")
    print(f"Total Variables Loaded: {len(all_vars)}")