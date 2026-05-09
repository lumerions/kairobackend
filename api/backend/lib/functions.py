from fastapi import Request
from fastapi.responses import JSONResponse
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from lib.getPostgresConn import *
from middleware.authMiddleware import *
from slowapi.util import get_remote_address

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
        secure =True,
        samesite = "Strict"
    )

    return response

async def getSessionKey(request : Request,serializer) -> str:
    Session = request.cookies.get("Session")
    ip = get_remote_address(request)

    if not Session:
        return f"ip{ip}"

    if not await sessionValid(serializer,Session):
        return f"ip{ip}"
    else:
        return f"Session{Session}"
    
def returnSerializedCookieData(Session,serializer) -> list:
    try:
        serializedData = serializer.loads(Session)
        UserId = int(serializedData.get("userId"))
        Version = int(serializedData.get("version"))
    except (ValueError,TypeError):
        return False
    
    if not UserId or not Version:
        return False
    
    return [UserId,Version]

async def getInventoryData(UserId : int) -> int:
    pool = await getpgPool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT items FROM users WHERE id = $1",
            UserId
        )

async def getFriendCount(UserId : int) -> int:
    pool = await getpgPool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT friendrequestscount FROM users WHERE id = $1",
            UserId
        )

async def getMessagesCount(UserId : int) -> int:
    pool = await getpgPool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT messagescount FROM users WHERE id = $1",
            UserId
        )
    
async def getTradesCount(UserId : int) -> int:
    pool = await getpgPool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT tradescount FROM users WHERE id = $1",
            UserId
        )
    
