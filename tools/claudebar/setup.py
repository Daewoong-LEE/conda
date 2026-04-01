"""
Setup script — supports both:
  • pip install -e .          (for development / direct execution)
  • python setup.py py2app    (to build a standalone macOS .app bundle)
"""
import sys
from pathlib import Path

from setuptools import find_packages, setup

# ── Common metadata ──────────────────────────────────────────────────────────
NAME        = "claudebar"
VERSION     = "0.1.0"
DESCRIPTION = "macOS status-bar app for real-time Claude token monitoring"
REQUIRES    = ["rumps>=0.4.0", "watchdog>=3.0.0"]

common = dict(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={"console_scripts": ["claudebar = claudebar.app:run"]},
)

# ── py2app (.app bundle) ─────────────────────────────────────────────────────
if "py2app" in sys.argv:
    extra = dict(
        app=["claudebar/__main__.py"],
        setup_requires=["py2app"],
        install_requires=REQUIRES,
        options={
            "py2app": {
                "argv_emulation": False,   # False = required for status-bar apps
                "packages": ["rumps", "watchdog"],
                "plist": {
                    "CFBundleName":              "ClaudeBar",
                    "CFBundleDisplayName":       "ClaudeBar",
                    "CFBundleIdentifier":        "com.claudebar.app",
                    "CFBundleVersion":           VERSION,
                    "CFBundleShortVersionString": VERSION,
                    "LSUIElement":               True,   # hide Dock icon
                    "NSHighResolutionCapable":   True,
                    "NSHumanReadableCopyright":  "MIT",
                },
            }
        },
    )
else:
    extra = dict(install_requires=REQUIRES)

setup(**common, **extra)
