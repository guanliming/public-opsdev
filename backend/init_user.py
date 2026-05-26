"""Create initial admin user."""
import asyncio
import sys
from app.database import init_db, async_session
from app.models import User
from app.auth import hash_password
from sqlalchemy import select


async def main():
    await init_db()
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin123"

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            return
        user = User(username=username, hashed_password=hash_password(password), display_name=username)
        db.add(user)
        await db.commit()
        print(f"Created user '{username}' with password '{password}'")


if __name__ == "__main__":
    asyncio.run(main())
