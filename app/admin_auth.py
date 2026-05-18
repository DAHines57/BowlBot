"""ADMIN_PIN gate for admin routes (alphanumeric; session or ?pin= / ?key=)."""
from __future__ import annotations

import os

from flask import request, session


def admin_pin_configured() -> bool:
    return bool(os.environ.get("ADMIN_PIN", "").strip())


def _supplied_pin() -> str:
    """PIN from ?pin=, ?key=, form, or X-Admin-Pin header."""
    return (
        (request.args.get("pin") or request.args.get("key") or "").strip()
        or (request.form.get("pin") or request.form.get("key") or "").strip()
        or (request.headers.get("X-Admin-Pin") or request.headers.get("X-Admin-Key") or "").strip()
    )


def check_admin_authorized() -> bool:
    """If ADMIN_PIN is set, require session unlock or matching pin on this request."""
    pin = os.environ.get("ADMIN_PIN", "").strip()
    if not pin:
        return True
    if session.get("admin_pin_ok"):
        return True
    supplied = _supplied_pin()
    if supplied and supplied == pin:
        session["admin_pin_ok"] = True
        return True
    return False


def unlock_admin() -> bool:
    pin = os.environ.get("ADMIN_PIN", "").strip()
    if not pin:
        session["admin_pin_ok"] = True
        return True
    supplied = _supplied_pin()
    if supplied == pin:
        session["admin_pin_ok"] = True
        return True
    return False
