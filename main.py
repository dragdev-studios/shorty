from random import choice
from string import ascii_letters, digits
from urllib.parse import quote_plus

import aiohttp
import aiosqlite
from fastapi import FastAPI, HTTPException, Header  #, Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Starlette is automatically installed with fastapi, but requirements plugin doesn't realise that.
# noinspection PyPackageRequirements
from starlette.background import BackgroundTask

import models
# from ratelimit import Bucket

allowed_statuses = list(range(100, 400))

usable = quote_plus(ascii_letters + digits)

sessions = {}

EMBED_DATA = """
<!DOCTYPE HTML>
<html>
<head>
<title>Shorty</title>
<meta name="description" value="A self-hosted link shortener and vanity provider."/>
<meta name="theme-color" value="#ffd866"/>
</head>
<body>
<h1>Uh?</h1>
<p>Our systems detected that you're a bot, and uh, we don't allow bots. If you're not a bot, then that sucks.</p>
<p>If you are a bot, go away.</p>
<p>With love, dragdev studios</p>
</body>
</html>
"""
EMBED_RESPONSE = HTMLResponse(EMBED_DATA, 403)

app = FastAPI(title="Shorty", description="Self-hosted link shortener that also serves as a vanity link provider.")
app.db = None


async def update_usage(serve, ua, src: str = "short"):
    if "Mozilla" not in ua:
        return  # safe bet that it was a bot crawling.
    await app.db.execute(
        """
        UPDATE ?
        SET uses=uses+1
        WHERE serve=?;""",
        (src, serve)
    )
    await app.db.commit()


@app.on_event("startup")
async def startup():
    app.db = await aiosqlite.connect("./main.db")
    await app.db.execute(
        """
        CREATE TABLE IF NOT EXISTS short (
            source TEXT NOT NULL,
            serve TEXT PRIMARY KEY,
            uses INT DEFAULT 0,
            expire TEXT DEFAULT '9999-12-31 23:59:59.999999',
            token TEXT NOT NULL
        );
        """
    )
    await app.db.execute(
        """
        CREATE TABLE IF NOT EXISTS vanity (
            source TEXT NOT NULL,
            serve TEXT PRIMARY KEY,
            uses INT DEFAULT 0,
            token TEXT NOT NULL
        );
        """
    )
    await app.db.commit()


@app.on_event("shutdown")
async def shutdown():
    await app.db.close()


# THIS DOESN'T WORK! WHY?!
# @app.middleware("http")
# async def set_session_cookie(request: Request, call_next):
#     print(sessions)
#     if _ses := request.cookies.get("session"):
#         if _ses in sessions.keys():
#             if sessions[_ses].ratelimited:
#                 raise HTTPException(
#                     429,
#                     "slow down!"
#                 )
#     response = await call_next(request)
#     if not request.cookies.get("session"):
#         response.set_cookie(
#             key="session",
#             value=str(hash(request.client))
#         )
#     elif (session := request.cookies["session"]) not in sessions.keys():
#         sessions[session] = Bucket(10, 60)
#         sessions[session].used += 1
#     return response


@app.get("/{path}")
async def get_vanity_or_shortened(path: str, user_agent: str = Header("No User Agent")):
    async with app.db.execute(
            """
            SELECT source FROM short WHERE serve=?
            """,
            (path,)
    ) as cursor:
        source = await cursor.fetchone()
        if not source:
            raise HTTPException(404, "Invalid code.")
        source = source[0]

    return RedirectResponse(source, 308, background=BackgroundTask(update_usage, source, user_agent, "short"))


@app.post("/s")
async def create_shortened_url(body: models.ShortenBody, host: str = Header(...)):
    """
    Creates a shortened URL.
    If you specify length. the output path will be that many characters long. By default it's 8."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(body.source) as response:
                if response.status not in allowed_statuses:
                    raise HTTPException(400, f"Invalid URL (got status {response.status})")
    except aiohttp.ClientError as e:
        raise HTTPException(400, f"Invalid URL (failed to connect, {e})")
    code = ''.join([choice(usable) for _ in range(body.length)])
    if not code or body.length < 3:
        raise HTTPException(400, "path length was too short.")
    shortened = models.Shortened(
        body.source,
        "None",
        models.Shortened.calculate_offset(body.expire or 999_999_999_999_999_999_999_999),
        0,
        "None",
        connection=app.db
    )
    try:
        await shortened.create(code)
    except aiosqlite.IntegrityError:
        raise HTTPException(
            400,
            "Too many links are using this length - Please increase."
        )
    return {
        "url": f"https://{host}/{code}",
        "code": code
    }


@app.delete("/s/{code}")
async def delete_shortened_code(code: str, token: str):
    """Deletes a shortened URL."""
    async with app.db.execute(
            """
            SELECT source, token FROM short WHERE serve=?
            """,
            (code,)
    ) as cursor:
        source = await cursor.fetchone()
        if not source:
            raise HTTPException(404, "Invalid code.")
        _, key = source
        if key != token:
            raise HTTPException(401, "Unauthorized")
    await app.db.execute("DELETE FROM short WHERE serve=?", (code,))
    await app.db.commit()
    return JSONResponse({}, 204)


@app.post("/v")
async def create_vanity_url(body: models.ShortenBody, host: str = Header(...)):
    """
    Creates a shortened URL.
    If you specify length. the output path will be that many characters long. By default it's 8."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(body.source) as response:
                if response.status not in allowed_statuses:
                    raise HTTPException(400, f"Invalid URL (got status {response.status})")
    except aiohttp.ClientError as e:
        raise HTTPException(400, f"Invalid URL (failed to connect, {e})")
    code = ''.join([choice(usable) for _ in range(body.length)])
    if not code or body.length < 4:
        raise HTTPException(400, "path length was too short.")
    shortened = models.Shortened(
        body.source,
        "None",
        models.Shortened.calculate_offset(body.expire or 999_999_999_999_999_999_999_999),
        0,
        "None",
        connection=app.db
    )
    try:
        await shortened.create(code)
    except aiosqlite.IntegrityError:
        raise HTTPException(
            400,
            "Too many links are using this length - Please increase."
        )
    return {
        "url": f"https://{host}/{code}",
        "code": code
    }


@app.delete("/v/{code}")
async def delete_vanity_code(code: str, token: str):
    """Deletes a shortened URL."""
    async with app.db.execute(
            """
            SELECT source, token FROM short WHERE serve=?
            """,
            (code,)
    ) as cursor:
        source = await cursor.fetchone()
        if not source:
            raise HTTPException(404, "Invalid code.")
        _, key = source
        if key != token:
            raise HTTPException(401, "Unauthorized")
    await app.db.execute("DELETE FROM short WHERE serve=?", (code,))
    await app.db.commit()
    return JSONResponse({}, 204)


app.mount("/", StaticFiles(directory="./static", html=True))
