"""Rules for what makes a user acceptable.

Pure functions returning error strings, so the same rules can be checked by the
interface before submitting and by the repository before writing, without
either one duplicating the other's logic.
"""
import re

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
USERNAME_MIN, USERNAME_MAX = 3, 32
DISPLAY_NAME_MAX = 64
PASSWORD_MIN = 8


class ValidationError(ValueError):
    """Raised when a user cannot be created as described."""


def check_username(username):
    username = (username or "").strip()
    if not username:
        return "Username is required."
    if len(username) < USERNAME_MIN:
        return f"Username must be at least {USERNAME_MIN} characters."
    if len(username) > USERNAME_MAX:
        return f"Username must be at most {USERNAME_MAX} characters."
    if not USERNAME_PATTERN.match(username):
        return "Username may only contain letters, numbers, underscore and hyphen."
    return None


def check_display_name(display_name):
    if display_name and len(display_name.strip()) > DISPLAY_NAME_MAX:
        return f"Display name must be at most {DISPLAY_NAME_MAX} characters."
    return None


def check_password(password, confirmation=None):
    if not password:
        return "Password is required."
    if len(password) < PASSWORD_MIN:
        return f"Password must be at least {PASSWORD_MIN} characters."
    if confirmation is not None and password != confirmation:
        return "Passwords do not match."
    return None


# returns the first problem found, or None when the input is usable
def check_new_user(username, display_name, password, confirmation=None):
    for problem in (
        check_username(username),
        check_display_name(display_name),
        check_password(password, confirmation),
    ):
        if problem:
            return problem
    return None
