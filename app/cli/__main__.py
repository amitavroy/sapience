import asyncio
import uuid

import typer
from sqlalchemy import text

from app.core.config import settings
from app.core.logger import logger
from app.core.trace import trace_id
from app.db.session import async_session_factory, engine
from app.schemas.user import UserCreate
from app.services import user as user_service

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Project management commands."""
    # one trace id per invocation; the contextvar carries into asyncio.run
    tid = uuid.uuid4().hex
    trace_id.set(tid)
    logger.configure(extra={"trace_id": tid})


async def _ping_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await engine.dispose()


@app.command()
def check_db() -> None:
    """Check that the database is reachable."""
    asyncio.run(_ping_db())
    typer.echo("database ok")


async def _seed_user(name: str, email: str, password: str) -> bool:
    async with async_session_factory() as db:
        try:
            await user_service.create_user(
                db, UserCreate(name=name, email=email, password=password)
            )
        except user_service.EmailTakenError:
            return False
        finally:
            await engine.dispose()
    return True


@app.command()
def seed_user(
    name: str = settings.seed_user_name,
    email: str = settings.seed_user_email,
    password: str = settings.seed_user_password,
    force: bool = typer.Option(False, help="Allow running when DEBUG is false."),
) -> None:
    """Create a user (dev only; idempotent)."""
    if not settings.debug and not force:
        typer.echo("refusing to seed: DEBUG is false (use --force)", err=True)
        raise typer.Exit(1)
    created = asyncio.run(_seed_user(name, email, password))
    typer.echo(f"user created: {email}" if created else "user exists")


if __name__ == "__main__":
    app()
