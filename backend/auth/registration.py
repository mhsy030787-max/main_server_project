import re


USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_]{4,32}$")
NAME_PATTERN = re.compile(r"^[가-힣a-zA-Z][가-힣a-zA-Z ]{1,29}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegistrationValidationError(ValueError):
    pass


def validate_password(password):
    password = str(password or "")
    if len(password) < 8 or len(password) > 128:
        raise RegistrationValidationError("비밀번호는 8~128자로 입력하세요.")

    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise RegistrationValidationError("비밀번호에는 영문과 숫자를 모두 포함하세요.")
    return password


def validate_registration(user_id, password, name, email):
    user_id = str(user_id or "").strip()
    name = " ".join(str(name or "").split())
    password = str(password or "")
    email = str(email or "").strip().lower()

    if not NAME_PATTERN.fullmatch(name):
        raise RegistrationValidationError(
            "이름은 한글 또는 영문 2~30자로 입력하세요."
        )

    if not USER_ID_PATTERN.fullmatch(user_id):
        raise RegistrationValidationError(
            "아이디는 영문, 숫자, 밑줄을 사용해 4~32자로 입력하세요."
        )

    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise RegistrationValidationError("사용할 수 있는 이메일 주소를 입력하세요.")

    password = validate_password(password)

    return {
        "user_id": user_id,
        "password": password,
        "name": name,
        "email": email,
        "role": "사원",
    }
