"""Default theme for the Super-MCP TUI."""

from __future__ import annotations

COLORS = {
    "primary": "#7C3AED",       # Violet
    "secondary": "#06B6D4",     # Cyan
    "accent": "#F59E0B",        # Amber
    "success": "#10B981",       # Emerald
    "warning": "#F59E0B",       # Amber
    "error": "#EF4444",         # Red
    "info": "#3B82F6",          # Blue
    "bg_dark": "#0F172A",       # Slate 900
    "bg_panel": "#1E293B",      # Slate 800
    "bg_surface": "#334155",    # Slate 700
    "text_primary": "#F8FAFC",  # Slate 50
    "text_secondary": "#94A3B8",# Slate 400
    "text_muted": "#64748B",    # Slate 500
    "border": "#475569",        # Slate 600
    "border_focus": "#7C3AED",  # Violet
}

# Textual CSS theme
THEME_CSS = """
Screen {
    background: $surface-darken-3;
}

#header-bar {
    dock: top;
    height: 3;
    background: $primary-darken-2;
    color: $text;
    text-style: bold;
    content-align: center middle;
    padding: 0 2;
}

#footer-bar {
    dock: bottom;
    height: 1;
    background: $primary-darken-3;
    color: $text-muted;
}

#main-content {
    layout: horizontal;
    height: 1fr;
}

#sidebar {
    width: 30;
    background: $surface-darken-2;
    border-right: solid $primary-darken-1;
    padding: 1;
}

#content-area {
    width: 1fr;
    layout: vertical;
}

#output-pane {
    height: 1fr;
    background: $surface-darken-3;
    padding: 1 2;
    overflow-y: scroll;
}

#input-area {
    dock: bottom;
    height: 3;
    background: $surface-darken-1;
    padding: 0 1;
}

#status-bar {
    dock: bottom;
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 2;
}

.panel-title {
    text-style: bold;
    color: $secondary;
    padding-bottom: 1;
}

.skill-item {
    padding: 0 1;
    height: 1;
}

.skill-item:hover {
    background: $primary-darken-1;
}

.tool-item {
    padding: 0 1;
    height: 1;
}

.tool-item.healthy {
    color: $success;
}

.tool-item.degraded {
    color: $warning;
}

.tool-item.down {
    color: $error;
}

.event-log-entry {
    padding: 0 1;
    height: auto;
}

.event-log-entry.info {
    color: $text;
}

.event-log-entry.warn {
    color: $warning;
}

.event-log-entry.error {
    color: $error;
}

.game-text {
    padding: 1;
    color: $text;
}

.game-prompt {
    color: $accent;
    text-style: bold;
}

.highlight {
    color: $accent;
    text-style: bold;
}

.muted {
    color: $text-muted;
}

.success-badge {
    color: $success;
    text-style: bold;
}

.error-badge {
    color: $error;
    text-style: bold;
}
"""
