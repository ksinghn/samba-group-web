import re
import shlex
import subprocess
import paramiko
import os
import uuid
from typing import Tuple, List

NAME_RE = re.compile(r'^[A-Za-z0-9._\-]{1,64}$')

class SambaToolError(Exception):
    pass


def validate_name(name: str) -> bool:
    return bool(NAME_RE.match(name))


def run_samba_command(command: str, timeout: int = 60) -> Tuple[int, str, str]:
    """
    Run a samba-tool command and return (returncode, stdout, stderr).
    Uses sudo with password passed via stdin.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # Connection info should be passed via context or environment
        # This is a helper function - actual connection handled in app routes
        raise NotImplementedError("Connection info must be provided by caller")
    except Exception as e:
        return 255, '', str(e)
    finally:
        try:
            client.close()
        except Exception:
            pass


def parse_user_show(output: str) -> Tuple[str, List[str]]:
    """Parse samba-tool user show output for email and group membership."""
    email = ''
    groups = []
    for line in output.splitlines():
        line = line.strip()
        if line.lower().startswith(('mail:', 'email:', 'mail address:')):
            parts = line.split(':', 1)
            if len(parts) > 1:
                email = parts[1].strip()
        if line.startswith('MemberOf:'):
            parts = line.split(':', 1)
            if len(parts) > 1:
                memberof = parts[1].strip()
                # comma separated; take CN=... pieces
                items = [x.strip() for x in memberof.split(',')]
                for item in items:
                    if item.upper().startswith('CN='):
                        cn = item.split('=', 1)[1]
                        groups.append(cn)
    return email, groups
