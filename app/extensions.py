"""Extensoes Flask compartilhadas (singletons)."""
from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager

login_manager: LoginManager = LoginManager()
limiter: Limiter = Limiter(key_func=get_remote_address, default_limits=[])
