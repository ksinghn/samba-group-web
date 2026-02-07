import os

class Config:
    SECRET_KEY = os.environ.get('SAMBA_GUI_SECRET_KEY', 'dev-secret-change-me')
    # Simple admin password for UI (use a stronger secret in production)
    ADMIN_PASSWORD = os.environ.get('SAMBA_GUI_ADMIN_PASSWORD', 'admin')
    # Session settings
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 3600
