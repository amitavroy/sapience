import asyncio
import uuid
from urllib.parse import urlsplit

import typer
from sqlalchemy import text

from app.core.config import settings
from app.core.logger import logger
from app.core.trace import trace_id
from app.db.session import async_session_factory, engine
from app.schemas.user import UserCreate
from app.services import collection as collection_service
from app.services import user as user_service
from app.tasks import crawler as crawler_tasks

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


async def _create_collection(
    name: str, description: str | None, owner_email: str | None
) -> tuple[int, str]:
    async with async_session_factory() as db:
        try:
            collection = await collection_service.create_collection(
                db, name, description, owner_email
            )
            return collection.id, collection.name
        finally:
            await engine.dispose()


@app.command()
def create_collection(
    name: str,
    description: str | None = typer.Option(None, help="Collection description."),
    owner_email: str | None = typer.Option(None, help="Email of the owning user."),
) -> None:
    """Create a collection and print its id."""
    try:
        collection_id, collection_name = asyncio.run(
            _create_collection(name, description, owner_email)
        )
    except collection_service.OwnerNotFoundError:
        typer.echo(f"user {owner_email} not found", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"collection created: {collection_id} ({collection_name})")


async def _collection_exists(collection_id: int) -> bool:
    async with async_session_factory() as db:
        try:
            return await collection_service.exists(db, collection_id)
        finally:
            await engine.dispose()


@app.command()
def crawl_url(url: str, collection: int = typer.Option(..., help="Collection id")) -> None:
    """Queue a crawl of one web page into a collection; results appear in the worker log."""
    if urlsplit(url).scheme not in ("http", "https"):
        typer.echo("url must start with http:// or https://", err=True)
        raise typer.Exit(1)
    if not asyncio.run(_collection_exists(collection)):
        typer.echo(f"collection {collection} not found", err=True)
        raise typer.Exit(1)
    crawler_tasks.crawl_url.delay(url, trace_id.get(), collection)
    typer.echo(f"queued: {url} (trace {trace_id.get()})")


if __name__ == "__main__":
    app()
