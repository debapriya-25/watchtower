"""Idempotent database seed script.

Seeds:
  * an **admin** user (credentials from ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD``),
  * a **demo** user (``DEMO_EMAIL`` / ``DEMO_PASSWORD``),
  * the top-N CoinGecko tokens into the catalogue (``TOP_TOKENS_COUNT``).

Safe to run repeatedly: existing users are left untouched and only missing
catalogue tokens are inserted (admin de-activations are preserved).

Usage (from the ``backend/`` directory)::

    python -m scripts.seed
    # or
    python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Allow ``python scripts/seed.py`` by putting ``backend/`` on the import path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# psycopg async needs a SelectorEventLoop on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal, dispose_engine  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.token import Token  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import coingecko  # noqa: E402
from app.services.coingecko import CoinGeckoError  # noqa: E402

logger = get_logger("seed")


async def _seed_user(
    db, *, email: str, password: str, role: UserRole, full_name: str
) -> bool:
    """Create a user if absent. Returns True if created."""
    existing = await db.scalar(select(User).where(User.email == email.lower()))
    if existing is not None:
        logger.info("seed_user_exists", email=email, role=role.value)
        return False

    db.add(
        User(
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
        )
    )
    await db.flush()
    logger.info("seed_user_created", email=email, role=role.value)
    return True


async def _seed_tokens(db) -> tuple[int, int]:
    """Insert any missing top-N CoinGecko tokens. Returns (inserted, skipped)."""
    markets = await coingecko.get_top_tokens(settings.top_tokens_count)

    existing_ids = set(
        (await db.execute(select(Token.coingecko_id))).scalars().all()
    )

    inserted = 0
    skipped = 0
    for entry in markets:
        coingecko_id = entry.get("id")
        symbol = (entry.get("symbol") or "").upper()
        name = entry.get("name")
        if not coingecko_id or not symbol or not name:
            continue
        if coingecko_id in existing_ids:
            skipped += 1
            continue
        db.add(
            Token(
                symbol=symbol[:32],
                name=name[:120],
                coingecko_id=coingecko_id,
                is_active=True,
            )
        )
        existing_ids.add(coingecko_id)
        inserted += 1

    await db.flush()
    return inserted, skipped


async def main() -> None:
    configure_logging()
    logger.info("seed_start", environment=settings.app_env)

    async with AsyncSessionLocal() as db:
        admin_created = await _seed_user(
            db,
            email=settings.admin_email,
            password=settings.admin_password,
            role=UserRole.ADMIN,
            full_name="Watchtower Admin",
        )
        demo_created = await _seed_user(
            db,
            email=settings.demo_email,
            password=settings.demo_password,
            role=UserRole.USER,
            full_name="Demo User",
        )

        inserted = skipped = 0
        token_error: str | None = None
        try:
            inserted, skipped = await _seed_tokens(db)
        except CoinGeckoError as exc:
            # Users are still seeded even if the price provider is unreachable.
            token_error = str(exc)
            logger.error("seed_tokens_failed", error=token_error)

        await db.commit()

    logger.info(
        "seed_complete",
        admin_created=admin_created,
        demo_created=demo_created,
        tokens_inserted=inserted,
        tokens_skipped=skipped,
    )

    print("\n=== Seed summary ===")
    print(f"  admin user : {settings.admin_email} "
          f"({'created' if admin_created else 'already existed'})")
    print(f"  demo user  : {settings.demo_email} "
          f"({'created' if demo_created else 'already existed'})")
    if token_error:
        print(f"  tokens     : FAILED to fetch from CoinGecko -> {token_error}")
    else:
        print(f"  tokens     : {inserted} inserted, {skipped} already present")
    print("====================\n")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
