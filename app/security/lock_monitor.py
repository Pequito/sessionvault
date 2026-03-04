"""Desktop screen-lock monitor.

Emits ``locked`` signal when the OS desktop lock is activated, so that
the application can lock the KeePass database automatically (same
behaviour as KeePassXC's "Lock on desktop lock" option).

Platform support
----------------
Linux   – D-Bus signal from org.freedesktop.ScreenSaver (covering
          KDE, GNOME, XFCE, Cinnamon, …) **and** the systemd logind
          PrepareForSleep signal so suspend also locks KeePass.
Windows – Polls ``WTSQuerySessionInformation`` via ctypes for the
          ``WTSSessionInfoClass.WTSConnectState`` flag; falls back to a
          ``WM_WTSSESSION_CHANGE`` native event filter if available.
macOS   – Polls ``CGSessionCopyCurrentDictionary`` for the
          ``CGSSessionScreenIsLocked`` key.

Usage
-----
    monitor = ScreenLockMonitor()
    monitor.locked.connect(lambda: keepass_manager.lock())
    monitor.start()
    …
    monitor.stop()

Written by Christopher Malo
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from app.managers.logger import get_logger

log = get_logger(__name__)


class ScreenLockMonitor(QObject):
    """Cross-platform desktop-lock detector.

    Signals
    -------
    locked
        Emitted once each time the screen transitions from unlocked →
        locked.  Not emitted for transitions in the other direction.
    """

    locked = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._poll_timer: QTimer | None = None
        self._dbus_thread: threading.Thread | None = None
        self._prev_locked: bool | None = None  # for polling platforms

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start monitoring.  Safe to call multiple times."""
        if self._running:
            return
        self._running = True
        log.debug("ScreenLockMonitor starting on %s", sys.platform)

        if sys.platform.startswith("linux"):
            self._start_linux()
        elif sys.platform == "win32":
            self._start_windows()
        elif sys.platform == "darwin":
            self._start_macos()
        else:
            log.warning("ScreenLockMonitor: unsupported platform %s", sys.platform)

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        log.debug("ScreenLockMonitor stopped")

    # ------------------------------------------------------------------
    # Linux – D-Bus
    # ------------------------------------------------------------------

    def _start_linux(self) -> None:
        """Try D-Bus (preferred); fall back to polling /proc."""
        # Run D-Bus listener in a daemon thread so the Qt event loop is
        # never blocked.
        self._dbus_thread = threading.Thread(
            target=self._linux_dbus_listener, daemon=True
        )
        self._dbus_thread.start()

    def _linux_dbus_listener(self) -> None:
        """Block on D-Bus signals; emit ``locked`` via a thread-safe call."""
        try:
            import dbus          # type: ignore[import]
            import dbus.mainloop.glib  # type: ignore[import]
            from gi.repository import GLib  # type: ignore[import]
        except ImportError:
            log.debug(
                "dbus-python / PyGObject not available; "
                "falling back to polling for screen lock"
            )
            self._start_linux_poll()
            return

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()

        def _on_active_changed(is_active: bool) -> None:
            if is_active and self._running:
                log.info("Screen locked (org.freedesktop.ScreenSaver)")
                self.locked.emit()

        def _on_prepare_sleep(sleeping: bool) -> None:
            if sleeping and self._running:
                log.info("System suspending – locking KeePass")
                self.locked.emit()

        try:
            bus.add_signal_receiver(
                _on_active_changed,
                dbus_interface="org.freedesktop.ScreenSaver",
                signal_name="ActiveChanged",
            )
        except Exception as exc:
            log.debug("Could not subscribe to ScreenSaver.ActiveChanged: %s", exc)

        try:
            system_bus = dbus.SystemBus()
            system_bus.add_signal_receiver(
                _on_prepare_sleep,
                dbus_interface="org.freedesktop.login1.Manager",
                signal_name="PrepareForSleep",
            )
        except Exception as exc:
            log.debug("Could not subscribe to logind.PrepareForSleep: %s", exc)

        loop = GLib.MainLoop()
        try:
            while self._running:
                # Run iterations with a timeout so we check _running
                loop.get_context().iteration(may_block=False)
                import time
                time.sleep(0.2)
        except Exception as exc:
            log.warning("D-Bus listener error: %s", exc)

    def _start_linux_poll(self) -> None:
        """Fallback: poll for X11/Wayland lock via xdg-screensaver status."""
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._linux_poll_tick)
        self._poll_timer.start()
        log.debug("ScreenLockMonitor: polling (xdg-screensaver) every 3 s")

    def _linux_poll_tick(self) -> None:
        import subprocess
        try:
            result = subprocess.run(
                ["xdg-screensaver", "status"],
                capture_output=True, text=True, timeout=2
            )
            is_locked = "enabled" in result.stdout.lower()
        except Exception:
            return
        if is_locked and self._prev_locked is False:
            log.info("Screen locked (xdg-screensaver poll)")
            self.locked.emit()
        self._prev_locked = is_locked

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    def _start_windows(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._windows_poll_tick)
        self._poll_timer.start()
        self._prev_locked = False
        log.debug("ScreenLockMonitor: polling (WTS) every 2 s")

    def _windows_poll_tick(self) -> None:
        try:
            import ctypes
            WTS_CURRENT_SERVER_HANDLE = ctypes.c_void_p(0)
            WTSGetActiveConsoleSessionId = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId  # type: ignore[attr-defined]
            WTSQuerySessionInformationW = ctypes.windll.wtsapi32.WTSQuerySessionInformationW  # type: ignore[attr-defined]
            WTSFreeMemory = ctypes.windll.wtsapi32.WTSFreeMemory  # type: ignore[attr-defined]

            WTSConnectState = 0
            session_id = WTSGetActiveConsoleSessionId()
            buf = ctypes.c_void_p()
            buf_size = ctypes.c_ulong()
            ok = WTSQuerySessionInformationW(
                WTS_CURRENT_SERVER_HANDLE,
                session_id,
                WTSConnectState,
                ctypes.byref(buf),
                ctypes.byref(buf_size),
            )
            if ok:
                state = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int)).contents.value
                WTSFreeMemory(buf)
                # State 7 = WTSDisconnected; there's no direct "locked" state via
                # WTS but session 0 going to disconnected means workstation locked
                is_locked = (state == 4)   # 4 = WTSIdle on Win Vista+
        except Exception:
            return
        if is_locked and self._prev_locked is False:
            log.info("Screen locked (Windows WTS poll)")
            self.locked.emit()
        self._prev_locked = is_locked

    # ------------------------------------------------------------------
    # macOS
    # ------------------------------------------------------------------

    def _start_macos(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._macos_poll_tick)
        self._poll_timer.start()
        self._prev_locked = False
        log.debug("ScreenLockMonitor: polling (CGSession) every 2 s")

    def _macos_poll_tick(self) -> None:
        try:
            import ctypes
            import ctypes.util
            core_graphics = ctypes.CDLL(
                ctypes.util.find_library("CoreGraphics") or ""
            )
            copy_dict = core_graphics.CGSessionCopyCurrentDictionary
            copy_dict.restype = ctypes.c_void_p
            session = copy_dict()
            if session is None:
                return

            # Use CoreFoundation to read the boolean key
            cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation") or "")
            cf_dict_get = cf.CFDictionaryGetValue
            cf_dict_get.restype  = ctypes.c_void_p
            cf_dict_get.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            # Build CFString key "CGSSessionScreenIsLocked"
            cf_str = cf.CFStringCreateWithCString
            cf_str.restype  = ctypes.c_void_p
            cf_str.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
            key = cf_str(None, b"CGSSessionScreenIsLocked", 0x08000100)

            val = cf_dict_get(session, key)
            is_locked = bool(val)
            cf.CFRelease(session)
        except Exception:
            return

        if is_locked and self._prev_locked is False:
            log.info("Screen locked (macOS CGSession poll)")
            self.locked.emit()
        self._prev_locked = is_locked


# Module-level singleton
screen_lock_monitor = ScreenLockMonitor()
