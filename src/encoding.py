"""UTF-8 output encoding setup for Windows terminals.

Call setup() at entry point to avoid garbled Chinese characters when
stdout is a GBK-coded terminal (cmd.exe / PowerShell).
"""
import sys


def setup():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # non-terminal (pipe/redirect) or platform without reconfigure
