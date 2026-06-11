#!/usr/bin/env python3
"""Generate VAPID keys for Web Push (dashboard PWA)."""

from __future__ import annotations

try:
    from py_vapid import Vapid
except ImportError:
    print("Install pywebpush first: pip install pywebpush")
    raise SystemExit(1)

vapid = Vapid()
vapid.generate_keys()
print("Add to Easypanel Environment:")
print(f"VAPID_PUBLIC_KEY={vapid.public_key}")
print(f"VAPID_PRIVATE_KEY={vapid.private_key}")
print("VAPID_CLAIMS_SUB=mailto:trade@martstudiosbr.com.br")
