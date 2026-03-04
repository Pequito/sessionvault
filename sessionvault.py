#!/usr/bin/env python3
"""SessionVault – SSH/RDP/VNC/Telnet client with integrated KeePass credential management.

This is the thin entry point for the application.  All application logic
lives in the app/ package.  Import and call app.main.main() to start.

Written by Christopher Malo
"""
"""SessionVault – SSH client with KeePass integration.

This file is the thin entry point.  All application logic lives in the
``app/`` package.
"""

from app.main import main

if __name__ == "__main__":
    main()
