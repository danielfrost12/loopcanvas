#!/usr/bin/env python3
"""
Canvas API Authentication Middleware

Two auth systems:
  1. Sign in with Apple — web UI sessions (cookie-based)
  2. API keys — programmatic access & GPU workers

API Key tiers:
  sk_test_*   → Test mode (all v2 endpoints, watermarked output)
  sk_live_*   → Live mode (all v2 endpoints, production output)
  sk_admin_*  → Admin (health, CMS, queue stats, + all v2)
  wk_*        → Worker tokens (queue claim/progress/complete/fail only)

Usage in server.py:
  from auth import CanvasAuth
  auth = CanvasAuth()

  # Web UI route (Sign in with Apple session):
  user = auth.require_session(self)
  if user is None:
      return  # 401 already sent

  # Programmatic API route:
  key = auth.require_api_key(self)

  # Accepts either session cookie OR API key:
  identity = auth.require_auth(self)

  # Admin routes:
  key = auth.require_admin(self)

  # Worker routes:
  token = auth.require_worker(self)
"""

import json
import time
import hmac
import hashlib
import secrets
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger('loopcanvas.auth')

# Key store location (gitignored)
KEYS_PATH = Path(__file__).parent / "keys.json"


class KeyInfo:
    """Parsed API key metadata."""
    __slots__ = ('key', 'mode', 'owner', 'created', 'tier')

    def __init__(self, key: str, mode: str, owner: str, created: str):
        self.key = key
        self.mode = mode
        self.owner = owner
        self.created = created
        # Derive tier from prefix
        if key.startswith("sk_admin_"):
            self.tier = "admin"
        elif key.startswith("sk_live_"):
            self.tier = "live"
        elif key.startswith("sk_test_"):
            self.tier = "test"
        else:
            self.tier = "unknown"

    @property
    def is_admin(self) -> bool:
        return self.tier == "admin"

    @property
    def is_live(self) -> bool:
        return self.tier in ("live", "admin")

    @property
    def prefix(self) -> str:
        """Safe prefix for logging (never log full key)."""
        return self.key[:12] + "..." if len(self.key) > 12 else self.key


class WorkerInfo:
    """Parsed worker token metadata."""
    __slots__ = ('token', 'worker_type', 'created')

    def __init__(self, token: str, worker_type: str, created: str):
        self.token = token
        self.worker_type = worker_type
        self.created = created

    @property
    def prefix(self) -> str:
        return self.token[:10] + "..." if len(self.token) > 10 else self.token


class AppleUser:
    """Authenticated Apple user from Sign in with Apple."""
    __slots__ = ('apple_id', 'email', 'name', 'session_token', 'created_at')

    def __init__(self, apple_id: str, email: str = "", name: str = "",
                 session_token: str = "", created_at: float = 0):
        self.apple_id = apple_id
        self.email = email
        self.name = name
        self.session_token = session_token
        self.created_at = created_at or time.time()


# ══════════════════════════════════════════════════════════════════
# Apple Sign In Configuration
# Set these env vars or they'll be read from keys.json "apple" block
# ══════════════════════════════════════════════════════════════════
# APPLE_CLIENT_ID     — your Services ID (e.g. com.loopcanvas.auth)
# APPLE_TEAM_ID       — your 10-char Apple Developer Team ID
# APPLE_KEY_ID        — Key ID from Apple Developer portal
# APPLE_PRIVATE_KEY   — path to .p8 private key file
# APPLE_REDIRECT_URI  — callback URL (e.g. https://canvas.yourdomain.com/auth/apple/callback)

APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"

# Session duration: 30 days
SESSION_MAX_AGE = 30 * 24 * 60 * 60


class CanvasAuth:
    """
    Authentication for the Canvas server.

    Supports:
      - Sign in with Apple (web UI sessions via cookie)
      - API keys (programmatic access)
      - Worker tokens (GPU worker communication)

    Loads keys from keys.json on init and on-demand reload.
    """

    def __init__(self, keys_path: Path = KEYS_PATH):
        self.keys_path = keys_path
        self._keys: Dict[str, Dict] = {}
        self._worker_tokens: Dict[str, Dict] = {}
        self._loaded_at: float = 0
        self._reload_interval: float = 60.0  # Re-check keys.json every 60s

        # Apple Sign In config
        self._apple_config: Dict[str, str] = {}

        # In-memory session store: session_token → AppleUser
        # In production, replace with Redis/DB
        self._sessions: Dict[str, AppleUser] = {}

        # Users store path (persisted to disk)
        self._users_path = keys_path.parent / "users.json"
        self._users: Dict[str, Dict] = {}  # apple_id → user data

        self._load_keys()
        self._load_users()

    def _load_keys(self):
        """Load or reload keys from disk."""
        try:
            if not self.keys_path.exists():
                logger.warning(f"[Auth] No keys file at {self.keys_path} — all routes UNPROTECTED")
                self._keys = {}
                self._worker_tokens = {}
                self._loaded_at = time.time()
                return

            data = json.loads(self.keys_path.read_text())
            self._keys = data.get("keys", {})
            self._worker_tokens = data.get("worker_tokens", {})
            self._loaded_at = time.time()
            logger.info(f"[Auth] Loaded {len(self._keys)} API keys, {len(self._worker_tokens)} worker tokens")

        except Exception as e:
            logger.error(f"[Auth] Failed to load keys: {e}")
            # Keep existing keys on reload failure
            if not self._keys and not self._worker_tokens:
                logger.critical("[Auth] No keys loaded — server has NO authentication")

    def _load_users(self):
        """Load persisted Apple users from disk."""
        try:
            if self._users_path.exists():
                self._users = json.loads(self._users_path.read_text())
                logger.info(f"[Auth] Loaded {len(self._users)} Apple users")
        except Exception as e:
            logger.error(f"[Auth] Failed to load users: {e}")

    def _save_users(self):
        """Persist Apple users to disk."""
        try:
            self._users_path.write_text(json.dumps(self._users, indent=2))
        except Exception as e:
            logger.error(f"[Auth] Failed to save users: {e}")

    def _maybe_reload(self):
        """Reload keys if stale."""
        if time.time() - self._loaded_at > self._reload_interval:
            self._load_keys()

    # ──────────────────────────────────────────────────────────────
    # Apple Sign In
    # ──────────────────────────────────────────────────────────────

    def get_apple_config(self) -> Dict[str, str]:
        """Get Apple Sign In config from env vars or keys.json."""
        import os
        config = self._apple_config
        if not config:
            # Try env vars first, then keys.json "apple" block
            keys_data = {}
            try:
                if self.keys_path.exists():
                    keys_data = json.loads(self.keys_path.read_text()).get("apple", {})
            except Exception:
                pass

            config = {
                "client_id": os.environ.get("APPLE_CLIENT_ID", keys_data.get("client_id", "")),
                "team_id": os.environ.get("APPLE_TEAM_ID", keys_data.get("team_id", "")),
                "key_id": os.environ.get("APPLE_KEY_ID", keys_data.get("key_id", "")),
                "private_key_path": os.environ.get("APPLE_PRIVATE_KEY", keys_data.get("private_key_path", "")),
                "redirect_uri": os.environ.get("APPLE_REDIRECT_URI", keys_data.get("redirect_uri", "")),
            }
            self._apple_config = config
        return config

    def get_apple_auth_url(self, state: str = "") -> str:
        """
        Build the Apple Sign In authorization URL.

        The frontend redirects the user here. Apple redirects back to
        our callback with an authorization code.
        """
        config = self.get_apple_config()
        if not state:
            state = secrets.token_urlsafe(32)

        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code id_token",
            "scope": "name email",
            "response_mode": "form_post",
            "state": state,
        }
        return f"{APPLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _generate_apple_client_secret(self) -> str:
        """
        Generate a client secret JWT for Apple token exchange.

        Apple requires a JWT signed with your .p8 private key.
        Uses PyJWT if available, otherwise returns empty (requires manual setup).
        """
        config = self.get_apple_config()
        try:
            import jwt  # PyJWT

            key_path = config.get("private_key_path", "")
            if not key_path or not Path(key_path).exists():
                logger.error("[Auth] Apple private key not found")
                return ""

            private_key = Path(key_path).read_text()

            now = int(time.time())
            payload = {
                "iss": config["team_id"],
                "iat": now,
                "exp": now + 86400 * 180,  # 6 months max
                "aud": "https://appleid.apple.com",
                "sub": config["client_id"],
            }
            headers = {
                "kid": config["key_id"],
                "alg": "ES256",
            }
            return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

        except ImportError:
            logger.error("[Auth] PyJWT not installed. Run: pip install PyJWT cryptography")
            return ""
        except Exception as e:
            logger.error(f"[Auth] Failed to generate Apple client secret: {e}")
            return ""

    def exchange_apple_code(self, authorization_code: str) -> Optional[Dict]:
        """
        Exchange Apple authorization code for tokens.

        Returns decoded ID token claims (sub, email, etc.) or None.
        """
        config = self.get_apple_config()
        client_secret = self._generate_apple_client_secret()
        if not client_secret:
            return None

        data = urllib.parse.urlencode({
            "client_id": config["client_id"],
            "client_secret": client_secret,
            "code": authorization_code,
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"],
        }).encode()

        req = urllib.request.Request(APPLE_TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                token_data = json.loads(resp.read().decode())

            # Decode the ID token (without verification for now — Apple's TLS is the trust)
            # In production, verify against Apple's public keys at APPLE_KEYS_URL
            id_token = token_data.get("id_token", "")
            if not id_token:
                logger.error("[Auth] No id_token in Apple response")
                return None

            # Decode JWT payload (base64, no signature verification here)
            import base64
            parts = id_token.split(".")
            if len(parts) != 3:
                return None
            # Pad base64
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))

            logger.info(f"[Auth] Apple token exchange successful for sub={claims.get('sub', '?')[:8]}...")
            return claims

        except Exception as e:
            logger.error(f"[Auth] Apple token exchange failed: {e}")
            return None

    def create_session(self, apple_id: str, email: str = "", name: str = "") -> str:
        """
        Create a session for an authenticated Apple user.

        Returns the session token (to be set as a cookie).
        """
        session_token = secrets.token_urlsafe(48)

        user = AppleUser(
            apple_id=apple_id,
            email=email,
            name=name,
            session_token=session_token,
        )
        self._sessions[session_token] = user

        # Persist user (upsert)
        if apple_id not in self._users:
            self._users[apple_id] = {
                "email": email,
                "name": name,
                "created": time.time(),
                "last_login": time.time(),
            }
        else:
            self._users[apple_id]["last_login"] = time.time()
            if email:
                self._users[apple_id]["email"] = email
            if name:
                self._users[apple_id]["name"] = name
        self._save_users()

        logger.info(f"[Auth] Session created for Apple user {apple_id[:8]}...")
        return session_token

    def get_session(self, handler) -> Optional[AppleUser]:
        """
        Get the authenticated user from session cookie.

        Returns AppleUser or None.
        """
        cookie_header = handler.headers.get("Cookie", "")
        session_token = None

        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("canvas_session="):
                session_token = part[len("canvas_session="):]
                break

        if not session_token:
            return None

        user = self._sessions.get(session_token)
        if not user:
            return None

        # Check expiry
        if time.time() - user.created_at > SESSION_MAX_AGE:
            del self._sessions[session_token]
            return None

        return user

    def destroy_session(self, handler):
        """Remove a session (logout)."""
        cookie_header = handler.headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("canvas_session="):
                token = part[len("canvas_session="):]
                self._sessions.pop(token, None)
                break

    # ──────────────────────────────────────────────────────────────
    # Unified auth (session OR API key)
    # ──────────────────────────────────────────────────────────────

    def require_session(self, handler) -> Optional[AppleUser]:
        """
        Require a valid Apple session cookie.

        Returns AppleUser on success, None on failure (401 sent).
        """
        user = self.get_session(handler)
        if user:
            return user

        client_ip = self._get_client_ip(handler)
        logger.warning(f"[Auth] No valid session from {client_ip} on {handler.path}")
        self._send_auth_error(handler, "Sign in required. Use Sign in with Apple.", 401)
        return None

    def require_auth(self, handler) -> Optional[Any]:
        """
        Accept either a session cookie OR an API key.

        Returns AppleUser or KeyInfo on success, None on failure (401 sent).
        Web UI sends cookies, programmatic clients send Bearer tokens.
        """
        # Try session first (web UI)
        user = self.get_session(handler)
        if user:
            return user

        # Try API key (programmatic)
        bearer = self._extract_bearer(handler)
        if bearer:
            key_info = self._lookup_api_key(bearer)
            if key_info:
                logger.info(f"[Auth] {key_info.prefix} ({key_info.tier}) → {handler.path}")
                return key_info

        # Neither worked
        # If no keys loaded (dev mode), allow
        if not self._keys:
            return KeyInfo(key="dev_mode", mode="test", owner="dev", created="")

        client_ip = self._get_client_ip(handler)
        logger.warning(f"[Auth] No valid auth from {client_ip} on {handler.path}")
        self._send_auth_error(handler, "Authentication required. Sign in with Apple or include Authorization: Bearer sk_...", 401)
        return None

    # ──────────────────────────────────────────────────────────────
    # Key lookup
    # ──────────────────────────────────────────────────────────────

    def _lookup_api_key(self, key: str) -> Optional[KeyInfo]:
        """Look up an API key. Returns KeyInfo or None."""
        self._maybe_reload()
        meta = self._keys.get(key)
        if meta:
            return KeyInfo(
                key=key,
                mode=meta.get("mode", "test"),
                owner=meta.get("owner", "unknown"),
                created=meta.get("created", ""),
            )
        return None

    def _lookup_worker_token(self, token: str) -> Optional[WorkerInfo]:
        """Look up a worker token. Returns WorkerInfo or None."""
        self._maybe_reload()
        meta = self._worker_tokens.get(token)
        if meta:
            return WorkerInfo(
                token=token,
                worker_type=meta.get("type", "unknown"),
                created=meta.get("created", ""),
            )
        return None

    def _extract_bearer(self, handler) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        auth_header = handler.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        return None

    def _extract_worker_token(self, handler) -> Optional[str]:
        """Extract worker token from X-Worker-Token header."""
        return handler.headers.get("X-Worker-Token", "").strip() or None

    def _get_client_ip(self, handler) -> str:
        """Get real client IP (Cloudflare-aware)."""
        # Cloudflare passes real IP in CF-Connecting-IP
        cf_ip = handler.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip
        # Fallback to X-Forwarded-For or direct IP
        xff = handler.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return handler.client_address[0] if handler.client_address else "unknown"

    # ──────────────────────────────────────────────────────────────
    # Auth enforcement (call from route handlers)
    # ──────────────────────────────────────────────────────────────

    def _send_auth_error(self, handler, message: str, status: int = 401):
        """Send a JSON auth error response."""
        body = json.dumps({
            "error": {
                "type": "authentication_error" if status == 401 else "authorization_error",
                "message": message,
            }
        })
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Access-Control-Allow-Origin',
                            handler.headers.get('Origin', '*'))
        handler.end_headers()
        handler.wfile.write(body.encode())

    def require_api_key(self, handler) -> Optional[KeyInfo]:
        """
        Require a valid sk_test_ / sk_live_ / sk_admin_ API key.

        Returns KeyInfo on success, None on failure (error already sent).
        """
        # If no keys loaded, allow all (dev mode)
        if not self._keys:
            return KeyInfo(key="dev_mode", mode="test", owner="dev", created="")

        token = self._extract_bearer(handler)
        if not token:
            client_ip = self._get_client_ip(handler)
            logger.warning(f"[Auth] Missing API key from {client_ip} on {handler.path}")
            self._send_auth_error(handler, "Missing API key. Include Authorization: Bearer sk_...", 401)
            return None

        key_info = self._lookup_api_key(token)
        if not key_info:
            client_ip = self._get_client_ip(handler)
            # Log prefix only for security
            prefix = token[:12] + "..." if len(token) > 12 else token
            logger.warning(f"[Auth] Invalid API key {prefix} from {client_ip} on {handler.path}")
            self._send_auth_error(handler, "Invalid API key provided", 401)
            return None

        logger.info(f"[Auth] {key_info.prefix} ({key_info.tier}) → {handler.path}")
        return key_info

    def require_admin(self, handler) -> Optional[KeyInfo]:
        """
        Require an sk_admin_ key.

        Returns KeyInfo on success, None on failure (error already sent).
        """
        key_info = self.require_api_key(handler)
        if key_info is None:
            return None  # 401 already sent

        if not key_info.is_admin:
            client_ip = self._get_client_ip(handler)
            logger.warning(f"[Auth] Non-admin key {key_info.prefix} attempted admin route {handler.path} from {client_ip}")
            self._send_auth_error(handler, "Admin access required. Use an sk_admin_ key.", 403)
            return None

        return key_info

    def require_worker(self, handler) -> Optional[WorkerInfo]:
        """
        Require a valid wk_ worker token via X-Worker-Token header.

        Returns WorkerInfo on success, None on failure (error already sent).
        """
        # If no worker tokens loaded, allow all (dev mode)
        if not self._worker_tokens:
            return WorkerInfo(token="dev_mode", worker_type="dev", created="")

        token = self._extract_worker_token(handler)
        if not token:
            client_ip = self._get_client_ip(handler)
            logger.warning(f"[Auth] Missing worker token from {client_ip} on {handler.path}")
            self._send_auth_error(handler, "Missing worker token. Include X-Worker-Token header.", 401)
            return None

        worker_info = self._lookup_worker_token(token)
        if not worker_info:
            client_ip = self._get_client_ip(handler)
            prefix = token[:10] + "..." if len(token) > 10 else token
            logger.warning(f"[Auth] Invalid worker token {prefix} from {client_ip} on {handler.path}")
            self._send_auth_error(handler, "Invalid worker token", 401)
            return None

        logger.info(f"[Auth] Worker {worker_info.prefix} ({worker_info.worker_type}) → {handler.path}")
        return worker_info
