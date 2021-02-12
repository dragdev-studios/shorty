import secrets

from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Union
from ratelimit import limits


# == HTTP MODELS == #


class ShortenBody(BaseModel):
    source: str
    length: int = Field(description="The length of the shortened output.", lt=10240, gt=3)
    secret: str
    expire: int = Field(description="After how many seconds to delete the shortened URL")


# == SQL MODELS == #


class Shortened:
    __schema__ = {
        "source": str,
        "serve": str,
        "expire": datetime,
        "uses": int,
        "token": str
    }

    def __init__(self, source: str, serve: str, expire: Union[datetime, str], uses: int, token: str, connection):
        self.source = source
        self.serve = serve
        self.expire = expire
        self.uses = uses
        if isinstance(self.expire, str):
            self.expire: datetime = self.parse_date(self.expire)
        self.connection = connection
        self.token = token

    @classmethod
    def parse_date(cls, datestring: str):
        try:
            return datetime.fromisoformat(datestring)
        except (ValueError, TypeError, Exception):
            return datetime.max

    @classmethod
    def calculate_offset(cls, offset: int):
        try:
            return datetime.utcnow() + timedelta(seconds=offset)
        except (ValueError, TypeError, Exception):
            return datetime.max

    @property
    def can_serve(self) -> bool:
        """A boolean indicating if the current URL can be served (I.E. not expired)."""
        return datetime.utcnow() < self.expire

    @limits(period=60)
    async def create(self, code: str):
        token = secrets.token_hex(64)
        args = (self.source, code, self.expire.isoformat(), token)
        self.token = token
        await self.connection.execute(
            """
            INSERT INTO short (source, serve, expire, token)
            VALUES (?, ?, ?, ?);
            """,
            args,
        )
        await self.connection.commit()
        return self

    @classmethod
    async def get(cls, *, key: str = "source", value, connection):
        args = (
            key,
            value
        )
        async with connection.execute("SELECT source, serve, expire, uses FROM short WHERE ?=?", args) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError("No row matching query.")
        return cls(*row, connection=connection)
