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
from config.Config import *
import json

config = Config()
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

def setUserSession(serializer,UserId : int,Username : str,Version : int):
    response = JSONResponse(content={"success":True})
    CookieValue = serializer.dumps({
        "userId": UserId,
        "userName": Username,
        "version": Version
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
        return ip.strip()
    
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    
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
        userName = str(serializedData.get("userName"))
    except (ValueError,TypeError):
        return False
    
    if not UserId or not Version:
        return False
    
    return [UserId,Version,userName]

def clearCookies(response):
    response.delete_cookie(
        key="Session",
        path="/",
        samesite="Strict"
    )
    response.delete_cookie(
        key="csrf",
        path="/",
        samesite="Strict"
    )
    return response

async def checkUserEmailLimit(Username : str) -> bool:
    dragonfly = await getDragonfly()
    emailCount = await dragonfly.get("r" + Username)

    if emailCount is None:
        dragonfly.set("r" + Username,1,ex = 900)
        return True
    
    if emailCount > 5:
        return False

    dragonfly.incr("r" + Username)
    return True

async def setSettingsData(data,UserId):
    dragonfly = await getDragonfly()
    await dragonfly.set(
        "SD" + str(UserId),
        json.dumps({ 
            "email": data["email"],
            "username": data["username"],
            "message_status": data["message_status"],
            "vip_server_status": data["vip_server_status"],
            "follow_status": data["follow_status"],
            "inventory_status": data["inventory_status"],
            "trade_status": data["trade_status"]
        }),
        ex = 86400
    )    

async def getIPData(IP):
    url = f"https://api.ipapi.com/{IP}"
    response = await client.get(url,params = {"access_key": config.IpapiKey}) 
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
    
