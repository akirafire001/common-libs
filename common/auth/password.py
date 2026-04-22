import bcrypt


def hash_password(plain: str) -> str:
    """パスワードをbcryptでハッシュ化して返す。"""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """平文パスワードとハッシュを照合する。"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())
