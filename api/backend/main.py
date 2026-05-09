from fastapi import FastAPI,Request,Cookie,Depends
from fastapi.responses import JSONResponse
from lib.schemas import *
from lib.functions import *
from lib.getPostgresConn import *
from lib.serializer import serializer
from config.Config import *
from itsdangerous import URLSafeSerializer
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from middleware.authMiddleware import sessionValid
from middleware.csrfMiddleware import *
import json

config = Config()
app = FastAPI()

async def LimiterKey(request: Request):
    return await getSessionKey(request, serializer)

userlimiter = Limiter(
    key_func = LimiterKey
)

app.state.limiter = userlimiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
async def RateLimited(request : Request,  exc : RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content = {
            "success":False,
            "message":"Too many requests!"
        }
    )

@app.get("/")
@userlimiter.limit("70/minute")
async def root(request : Request):
    return {"message":"hi"}

@app.get("/api/friendcount",dependencies=[Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def friendcount(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]

    return await getFriendCount(UserId)

@app.get("/api/messagescount")
@userlimiter.limit("70/minute")
async def messagescount(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]

    return await getMessagesCount(UserId)

@app.get("/api/tradescount")
@userlimiter.limit("70/minute")
async def tradecount(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]

    return await getTradesCount(UserId)

@app.get("/api/inventory")
@userlimiter.limit("70/minute")
async def inventory(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]

    return await getInventoryData(UserId)

@app.post("/api/register")
@userlimiter.limit("15/minute")
async def register(request : Request,data : RegisterSchema,Session : str = Cookie(None)):
    Username = data.Username
    Password = data.Password
    ConfirmPassword = data.ConfirmPassword

    if Session:
        return {"success":False,"message": "Please log out before attempting to log in."}
    
    if (len(Password) < 8):
        return {"success":False,"message": "Password must be atleast 8 characters."}

    if Password != ConfirmPassword:
        return {"success":False,"message": "Password and Confirm password must be the same!"}
    
    if not UserNameValid(Username):
        return {"success":False,"message": "Usernames can only have 3 to 20 characters, consisting of numbers, letters, and up to one underscore."}

    pgPool = await getpgPool()
    PasswordHash = argon2Hash(Password)

    async with pgPool.acquire() as conn:
        async with conn.transaction():
            UserId = await conn.fetchval("""
                WITH new_user AS (
                    INSERT INTO users (
                        username, password, email,
                        friendrequestscount, messagescount,
                        messages, admin, equippeditems,version
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    RETURNING id
                )
                INSERT INTO balances (userid, robux)
                SELECT id, 0 FROM new_user
                RETURNING userid
            """,
            Username,
            PasswordHash,
            "",
            0,
            0,
            json.dumps([]),
            False,
            json.dumps([]),
            "1"
            )

            if UserId is None:
                return {"success":False,"message": "Something went wrong registering, please try again later."}
            else:
                return setUserSession(serializer,UserId,Username)

@app.post("/api/login")
@userlimiter.limit("15/minute")
async def login(request : Request,data : LoginSchema, Session : str = Cookie(None)):
    Username = data.Username
    Password = data.Password

    if Session:
        return {"success":False,"message": "Please log out before attempting to log in."}

    pgPool = await getpgPool()

    async with pgPool.acquire() as conn:
        user = await conn.fetchrow(""" 
            SELECT id, username, password, email
            FROM users
            WHERE username = $1                  
        """, Username)

        if user is None:
            return {"success":False,"message": "Invalid username or password."}

        if not argon2Verify(user["password"],Password):
            return {"success":False,"message": "Invalid username or password."}

        return setUserSession(serializer,user["id"],Username)
