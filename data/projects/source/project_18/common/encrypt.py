import base64


def encode_password(password: str) -> str:
    return base64.b64encode(password.encode()).decode()
