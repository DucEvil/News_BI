"""Thông báo CLI ngắn cho lỗi lồng nhau của MCP SDK."""


def failure_message(exc):
    children=getattr(exc,'exceptions',None)
    if children:
        return '; '.join(dict.fromkeys(failure_message(child) for child in children))
    message=str(exc)
    if 'superset_http_401' in message and '/api/v1/security/login' in message:
        return ('Superset login rejected (401). The account password stored in Superset does not match '
                'SUPERSET_ADMIN_PASSWORD, or the account is inactive/missing. '
                'Check the login password in .env; to explicitly synchronize it, use '
                'scripts/start-ai.ps1 -SyncAdminPassword.')
    return message[:500]
