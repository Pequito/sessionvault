"""Application-wide constants: paths, metadata, and color palettes."""

from __future__ import annotations

import pathlib

APP_NAME = "SessionVault"
APP_VERSION = "2.0.0"
DATA_DIR = pathlib.Path.home() / ".sessionvault"
SESSIONS_FILE = DATA_DIR / "sessions.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
MACROS_FILE = DATA_DIR / "macros.json"
PLUGINS_DIR = DATA_DIR / "plugins"

# ---------------------------------------------------------------------------
# Catppuccin Mocha (default dark theme)
# ---------------------------------------------------------------------------
MOCHA: dict[str, str] = {
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

# ---------------------------------------------------------------------------
# Catppuccin Latte (light theme)
# ---------------------------------------------------------------------------
LATTE: dict[str, str] = {
    "base":      "#eff1f5",
    "mantle":    "#e6e9ef",
    "crust":     "#dce0e8",
    "surface0":  "#ccd0da",
    "surface1":  "#bcc0cc",
    "surface2":  "#acb0be",
    "overlay0":  "#9ca0b0",
    "overlay1":  "#8c8fa1",
    "overlay2":  "#7c7f93",
    "subtext0":  "#6c6f85",
    "subtext1":  "#5c5f77",
    "text":      "#4c4f69",
    "lavender":  "#7287fd",
    "blue":      "#1e66f5",
    "sapphire":  "#209fb5",
    "sky":       "#04a5e5",
    "teal":      "#179299",
    "green":     "#40a02b",
    "yellow":    "#df8e1d",
    "peach":     "#fe640b",
    "maroon":    "#e64553",
    "red":       "#d20f39",
    "mauve":     "#8839ef",
    "pink":      "#ea76cb",
    "flamingo":  "#dd7878",
    "rosewater": "#dc8a78",
}

# ---------------------------------------------------------------------------
# Dracula
# ---------------------------------------------------------------------------
DRACULA: dict[str, str] = {
    "base":      "#282a36",
    "mantle":    "#21222c",
    "crust":     "#191a21",
    "surface0":  "#343746",
    "surface1":  "#3d4053",
    "surface2":  "#454862",
    "overlay0":  "#6272a4",
    "overlay1":  "#7281b0",
    "overlay2":  "#818fbb",
    "subtext0":  "#a0aec0",
    "subtext1":  "#b0bcd0",
    "text":      "#f8f8f2",
    "lavender":  "#bd93f9",
    "blue":      "#6272a4",
    "sapphire":  "#8be9fd",
    "sky":       "#8be9fd",
    "teal":      "#8be9fd",
    "green":     "#50fa7b",
    "yellow":    "#f1fa8c",
    "peach":     "#ffb86c",
    "maroon":    "#ff5555",
    "red":       "#ff5555",
    "mauve":     "#bd93f9",
    "pink":      "#ff79c6",
    "flamingo":  "#ff79c6",
    "rosewater": "#ffb86c",
}

# ---------------------------------------------------------------------------
# Nord
# ---------------------------------------------------------------------------
NORD: dict[str, str] = {
    "base":      "#2e3440",
    "mantle":    "#292e39",
    "crust":     "#242933",
    "surface0":  "#3b4252",
    "surface1":  "#434c5e",
    "surface2":  "#4c566a",
    "overlay0":  "#616e88",
    "overlay1":  "#6d7f99",
    "overlay2":  "#7a8fa8",
    "subtext0":  "#8fa4b5",
    "subtext1":  "#a4b5c2",
    "text":      "#d8dee9",
    "lavender":  "#b48ead",
    "blue":      "#81a1c1",
    "sapphire":  "#5e81ac",
    "sky":       "#88c0d0",
    "teal":      "#8fbcbb",
    "green":     "#a3be8c",
    "yellow":    "#ebcb8b",
    "peach":     "#d08770",
    "maroon":    "#bf616a",
    "red":       "#bf616a",
    "mauve":     "#b48ead",
    "pink":      "#b48ead",
    "flamingo":  "#d08770",
    "rosewater": "#d08770",
}

# ---------------------------------------------------------------------------
# One Dark
# ---------------------------------------------------------------------------
ONE_DARK: dict[str, str] = {
    "base":      "#282c34",
    "mantle":    "#21252b",
    "crust":     "#1b1f27",
    "surface0":  "#31353f",
    "surface1":  "#3a3f4b",
    "surface2":  "#434852",
    "overlay0":  "#545862",
    "overlay1":  "#636773",
    "overlay2":  "#737880",
    "subtext0":  "#848891",
    "subtext1":  "#9da5b4",
    "text":      "#abb2bf",
    "lavender":  "#c678dd",
    "blue":      "#61afef",
    "sapphire":  "#56b6c2",
    "sky":       "#56b6c2",
    "teal":      "#56b6c2",
    "green":     "#98c379",
    "yellow":    "#e5c07b",
    "peach":     "#d19a66",
    "maroon":    "#e06c75",
    "red":       "#e06c75",
    "mauve":     "#c678dd",
    "pink":      "#c678dd",
    "flamingo":  "#e06c75",
    "rosewater": "#d19a66",
}

# Registry of all built-in themes
THEMES: dict[str, dict[str, str]] = {
    "Catppuccin Mocha": MOCHA,
    "Catppuccin Latte": LATTE,
    "Dracula":          DRACULA,
    "Nord":             NORD,
    "One Dark":         ONE_DARK,
}

# Active palette – mutated at runtime by apply_theme()
C: dict[str, str] = dict(MOCHA)


def _ansi_16(palette: dict) -> list[str]:
    """Build the standard 16-color ANSI palette from a theme palette."""
    return [
        palette["surface1"],  # 0  black
        palette["red"],       # 1  red
        palette["green"],     # 2  green
        palette["yellow"],    # 3  yellow
        palette["blue"],      # 4  blue
        palette["mauve"],     # 5  magenta
        palette["teal"],      # 6  cyan
        palette["text"],      # 7  white
        palette["surface2"],  # 8  bright black
        palette["red"],       # 9  bright red
        palette["green"],     # 10 bright green
        palette["yellow"],    # 11 bright yellow
        palette["blue"],      # 12 bright blue
        palette["mauve"],     # 13 bright magenta
        palette["teal"],      # 14 bright cyan
        palette["text"],      # 15 bright white
    ]


# Standard 8 + bright-8 ANSI terminal colors (mutable – updated by apply_theme)
ANSI_COLORS_16: list[str] = _ansi_16(MOCHA)

# Mutable cache populated lazily by app.terminal.ansi
ANSI_256_CACHE: dict[int, str] = {}
