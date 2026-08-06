import secrets
import sys

from app.database import SessionLocal
from app.models import ApiKey
from app.security import hash_key


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "default"
    raw = secrets.token_urlsafe(32)
    with SessionLocal() as session:
        session.add(ApiKey(name=name, key_hash=hash_key(raw)))
        session.commit()
    print(raw)


if __name__ == "__main__":
    main()
