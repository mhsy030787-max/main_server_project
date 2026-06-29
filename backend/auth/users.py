from security.passwords import hash_password


def make_user(user_id, password, name, role):
    return {
        "id": user_id,
        "name": name,
        "role": role,
        "password": hash_password(password),
    }


def public_user(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "role": user["role"],
    }


DEFAULT_USERS = {
    "admin": make_user("admin", "1234", "관리자", "관리자"),
    "leader": make_user("leader", "1234", "팀장", "팀장"),
    "staff": make_user("staff", "1234", "사원", "사원"),
}
