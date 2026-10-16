"""Per-user PIN so one person cannot read another user's memory by typing their ID.
First use of an ID registers the PIN; later uses must match. Memory stays locked until verified."""
import hashlib
import hmac
import os

from . import procedural_store as ps

MIN_PIN = 4
ITERATIONS = 200_000


def _hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ITERATIONS)


def unlock(user_id, pin):
    """Return 'registered', 'ok' or a failure code: 'bad_user', 'weak_pin', 'denied', 'unavailable'."""
    if not ps.valid_user_id(user_id):
        return "bad_user"
    pin = str(pin or "")
    if len(pin) < MIN_PIN:
        return "weak_pin"
    try:
        with ps._connect() as conn:
            ps._ensure(conn)
            row = conn.execute(f"SELECT salt, pin_hash FROM {ps.SCHEMA}.users WHERE user_id = %s",
                               (user_id,)).fetchone()
            if row is None:
                salt = os.urandom(16)
                conn.execute(f"INSERT INTO {ps.SCHEMA}.users (user_id, salt, pin_hash) VALUES (%s, %s, %s)",
                             (user_id, salt, _hash(pin, salt)))
                return "registered"
            salt, stored = bytes(row[0]), bytes(row[1])
        return "ok" if hmac.compare_digest(_hash(pin, salt), stored) else "denied"
    except Exception:
        return "unavailable"


def delete_user(user_id):
    try:
        with ps._connect() as conn:
            ps._ensure(conn)
            conn.execute(f"DELETE FROM {ps.SCHEMA}.users WHERE user_id = %s", (user_id,))
        return True
    except Exception:
        return False
