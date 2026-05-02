"""LDAP client — тонкая обёртка над ldap3 для операций с OpenLDAP."""
import structlog
from ldap3 import ALL, MODIFY_REPLACE, Connection, Server

from app.config import settings

logger = structlog.get_logger()


def _connect() -> Connection:
    server = Server(settings.LDAP_URI, get_info=ALL)
    conn = Connection(server, user=settings.LDAP_BIND_DN, password=settings.LDAP_BIND_PASSWORD, auto_bind=True)
    return conn


def _ensure_ou(conn: Connection, ou: str) -> None:
    """Create OU under ou=people if it doesn't exist."""
    ou_dn = f"ou={ou},ou=people,{settings.LDAP_BASE_DN}"
    conn.add(ou_dn, object_class=["organizationalUnit"], attributes={"ou": ou})


def ldap_create_user(username: str, full_name: str, email: str, department_code: str | None = None) -> str:
    """Add user to LDAP, return the DN."""
    conn = _connect()
    try:
        dept_ou = department_code or "people"
        _ensure_ou(conn, dept_ou)

        dn = f"uid={username},ou={dept_ou},ou=people,{settings.LDAP_BASE_DN}"
        parts = full_name.split()
        sn = parts[-1] if parts else username

        conn.add(
            dn,
            object_class=["inetOrgPerson", "organizationalPerson", "person", "top"],
            attributes={
                "cn": full_name,
                "sn": sn,
                "uid": username,
                "mail": email,
            },
        )
        if conn.result["result"] not in (0, 68):  # 68 = entryAlreadyExists
            logger.warning("ldap_add_unexpected_result", result=conn.result, dn=dn)
        return dn
    finally:
        conn.unbind()


def ldap_modify_user(ldap_dn: str, cn: str | None = None, mail: str | None = None) -> None:
    changes: dict = {}
    if cn:
        changes["cn"] = [(MODIFY_REPLACE, [cn])]
    if mail:
        changes["mail"] = [(MODIFY_REPLACE, [mail])]
    if not changes:
        return
    conn = _connect()
    try:
        conn.modify(ldap_dn, changes)
    finally:
        conn.unbind()


def ldap_block_user(ldap_dn: str) -> None:
    """Lock account via pwdAccountLockedTime (requires ppolicy overlay)."""
    conn = _connect()
    try:
        conn.modify(ldap_dn, {"pwdAccountLockedTime": [(MODIFY_REPLACE, ["000001010000Z"])]})
    finally:
        conn.unbind()


def ldap_unblock_user(ldap_dn: str) -> None:
    conn = _connect()
    try:
        conn.modify(ldap_dn, {"pwdAccountLockedTime": [(MODIFY_REPLACE, [])]})
    finally:
        conn.unbind()


def ldap_delete_user(ldap_dn: str) -> None:
    conn = _connect()
    try:
        conn.delete(ldap_dn)
    finally:
        conn.unbind()


def ldap_reset_password(ldap_dn: str, new_password: str) -> None:
    conn = _connect()
    try:
        conn.modify(ldap_dn, {"userPassword": [(MODIFY_REPLACE, [new_password])]})
    finally:
        conn.unbind()
