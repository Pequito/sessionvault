"""Application-wide constants: paths, metadata, and Catppuccin Mocha palette."""

from __future__ import annotations

import pathlib

APP_NAME = "SessionVault"
APP_VERSION = "1.0.0"
DATA_DIR = pathlib.Path.home() / ".sessionvault"
SESSIONS_FILE = DATA_DIR / "sessions.json"

# ---------------------------------------------------------------------------
# Catppuccin Mocha color palette
# ---------------------------------------------------------------------------
C: dict[str, str] = {
    "base":      "#1e1e2e",
    "mantle":    "#181825",
    "crust":     "#11111b",
    "surface0":  "#313244",
    "surface1":  "#45475a",
    "surface2":  "#585b70",
    "overlay0":  "#6c7086",
    "overlay1":  "#7f849c",
    "overlay2":  "#9399b2",
    "subtext0":  "#a6adc8",
    "subtext1":  "#bac2de",
    "text":      "#cdd6f4",
    "lavender":  "#b4befe",
    "blue":      "#89b4fa",
    "sapphire":  "#74c7ec",
    "sky":       "#89dceb",
    "teal":      "#94e2d5",
    "green":     "#a6e3a1",
    "yellow":    "#f9e2af",
    "peach":     "#fab387",
    "maroon":    "#eba0ac",
    "red":       "#f38ba8",
    "mauve":     "#cba6f7",
    "pink":      "#f5c2e7",
    "flamingo":  "#f2cdcd",
    "rosewater": "#f5e0dc",
}

# Standard 8 + bright-8 ANSI terminal colors mapped to Catppuccin Mocha
ANSI_COLORS_16: list[str] = [
    C["surface1"],   # 0  black
    C["red"],        # 1  red
    C["green"],      # 2  green
    C["yellow"],     # 3  yellow
    C["blue"],       # 4  blue
    C["mauve"],      # 5  magenta
    C["teal"],       # 6  cyan
    C["text"],       # 7  white
    C["surface2"],   # 8  bright black
    C["red"],        # 9  bright red
    C["green"],      # 10 bright green
    C["yellow"],     # 11 bright yellow
    C["blue"],       # 12 bright blue
    C["mauve"],      # 13 bright magenta
    C["teal"],       # 14 bright cyan
    C["text"],       # 15 bright white
]

# Mutable cache populated lazily by app.terminal.ansi
ANSI_256_CACHE: dict[int, str] = {}
