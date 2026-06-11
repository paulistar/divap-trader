#!/usr/bin/env python3
"""Generate VAPID keys for Web Push (dashboard PWA)."""

from __future__ import annotations

import base64

try:
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
except ImportError:
    print("Install pywebpush first: pip install pywebpush")
    raise SystemExit(1)

vapid = Vapid()
vapid.generate_keys()

private_pem = vapid.private_pem().decode()
public_bytes = vapid.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
public_b64url = base64.urlsafe_b64encode(public_bytes).decode().rstrip("=")

print("Add to Easypanel Environment:")
print(f"VAPID_PUBLIC_KEY={public_b64url}")
print(f"VAPID_PRIVATE_KEY={private_pem.replace(chr(10), '\\n')}")
print("VAPID_CLAIMS_SUB=mailto:trade@martstudiosbr.com.br")
