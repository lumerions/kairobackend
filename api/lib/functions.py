from fastapi import Request
from fastapi.responses import JSONResponse
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from lib.getPostgresConn import *
from middleware.authMiddleware import *
from typing import Optional
from lib.dragonflydb import *
import httpx
client = httpx.AsyncClient(timeout = 5)

Ph = PasswordHasher()

def argon2Hash(text : str) -> str:
    return Ph.hash(text)

def argon2Verify(hash : str,text : str) -> bool:
    try:
        return Ph.verify(hash,text)
    except VerifyMismatchError:
        return False
    
def UserNameValid(Username : str) -> bool:
    if len(Username) < 3 or len(Username) > 20:
        return False

    if not Username.replace("_","").isalnum():
        return False

    if Username.count("_") > 1:
        return False
    
    return True

def setUserSession(serializer,UserId,Username):
    response = JSONResponse(content={"success":True})
    CookieValue = serializer.dumps({
        "userId": UserId,
        "userName": Username,
        "version": "1"
    })

    response.set_cookie(
        key = "Session",
        value = CookieValue,
        max_age = 63072000,
        httponly = True,
        secure = True,
        samesite = "Strict"
    )

    return response

def getUserIP(request: Request):
    ip = request.headers.get("cf-connecting-ip")
    if ip:
        return ip
    
    xss = request.headers.get("x-forwarded-for")
    if xss:
        return xss.split(",")[0].strip()
    
    return request.client.host

async def getSessionKey(request : Request,serializer) -> str:
    Session = request.cookies.get("Session")
    ip = getUserIP(request)

    if not Session:
        return f"ip{ip}"

    if not await sessionValid(serializer,Session):
        return f"ip{ip}"
    else:
        return f"Session{Session}"
    
def returnSerializedCookieData(Session,serializer) -> Optional[list]:
    try:
        serializedData = serializer.loads(Session)
        UserId = int(serializedData.get("userId"))
        Version = int(serializedData.get("version"))
    except (ValueError,TypeError):
        return False
    
    if not UserId or not Version:
        return False
    
    return [UserId,Version]


async def clearCookies(response):
    response.delete_cookie(key = "Session", path = "/")
    response.delete_cookie(key = "csrf", path = "/")
    return response

async def getIPData(IP):
    url = f"https://ipapi.co/{IP}/json/"
    response = await client.get(url) 
    response.raise_for_status()
    return response.json()

async def getInventoryData(UserId : int) -> list:
    pool = await getpgPool()
    async with pool.acquire() as conn:
        items = await conn.fetchval(
            "SELECT items FROM users WHERE id = $1",
            UserId
        ) or []
        return items
    
async def getBalance(UserId : int) -> Optional[int]:
    pool = await getpgPool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT robux FROM balances WHERE userid = $1",
            UserId
        )
    
async def getUsernameByUserId(UserId : int) -> Optional[str]:
    dragonfly = await getDragonfly()
    dragonFlyUsername = await dragonfly.get(str(UserId))

    if dragonFlyUsername:
        return dragonFlyUsername
    
    pool = await getpgPool()
    async with pool.acquire() as conn:
        username = await conn.fetchval(
            "SELECT username FROM users WHERE id = $1",
            UserId
        )
    
        await dragonfly.set(str(UserId),username,ex = 86400)

    
async def getUserIdByUsername(UserName : str)  -> Optional[str]:
    dragonfly = await getDragonfly()
    dragonFlyUserId = await dragonfly.get(UserName)

    if dragonFlyUserId:
        return dragonFlyUserId

    pool = await getpgPool()
    async with pool.acquire() as conn:
        UserId = await conn.fetchval(
            "SELECT id FROM users WHERE username = $1",
            UserName
        )

        await dragonfly.set(UserName,UserId,ex = 86400)
        return UserId
    
