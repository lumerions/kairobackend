from fastapi import FastAPI,Request,Cookie,Depends
from fastapi.responses import JSONResponse
from lib.schemas import *
from lib.functions import *
from lib.getPostgresConn import *
from lib.serializer import serializer
from config.Config import *
from lib.messages import *
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from middleware.authMiddleware import sessionValid
from middleware.csrfMiddleware import *
import json
import uuid
from datetime import datetime,timezone,timedelta

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
            "success" : False,
            "message" : "Too many requests!"
        }
    )

@app.exception_handler(HTTPException)
async def Unauthorized(request : Request,exc : HTTPException):
    response = JSONResponse(status_code = exc.status_code, content = {"success":False,"message": exc.detail})
    if exc.status_code == 403:
        response = await clearCookies(response)
        return response

@app.get("/api/messages",dependencies = [Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def messages(request : Request,Session : str = Cookie(None),tab : str = "Inbox",page : int = 1):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]
    offset = (page - 1) * 10
    Messages, TotalPageCount = await getMessagesByType(UserId, offset, tab)
    FormattedData = []

    for item in Messages:
        Message = item["elem"]

        if isinstance(Message,str):
            Message = json.loads(Message)

        FormattedData.append(Message)

    return {
        "success":True,
        "data": FormattedData,
        "currentPage": page,
        "totalPages": (TotalPageCount + 10 - 1) if TotalPageCount else 1,
    }

@app.get("/api/messages/details",dependencies=[Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def messagedetail(request : Request,Session : str = Cookie(None),id : str = None):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]

    if id:
        Message = await getSingularMessageById(id,UserId)

        if not Message:
            return {"success": False,"message": "Message doesn't exist."}

        print(Message)
        
        MessageData = Message["elem"]
 
        if isinstance(MessageData, str):
            MessageData = json.loads(MessageData)

        print(MessageData)

        SendUserId = await getUserIdByUsername(MessageData["sender"])

        if not SendUserId:
            return {"success": False,"message": "Player doesn't exist."}

        return {
            "success": True,
            "content": MessageData["text"],
            "timestamp": MessageData["createdat"],
            "userid": SendUserId
        }
    else:
        return {"success":False,"message": "Please provide a message id."}

@app.get("/api/authenticated")
@userlimiter.limit("70/minute")
async def authenticated(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    await sessionValid(request,Session)

    UserId = CookieData[0]

    dragonfly = await getDragonfly()
    dragonFlyData = await dragonfly.get("AuthData" + str(UserId))

    if dragonFlyData:
        AuthData = json.loads(dragonFlyData)
        AuthData["success"] = True
        return AuthData

    pool = await getpgPool()
    async with pool.acquire() as conn:
        data = await conn.fetchrow(
            """
            WITH lastseenupdate AS (
                UPDATE users
                SET last_seen = NOW()
                WHERE id = $1
            ),

            updated AS (
                UPDATE membership
                SET created_at = NOW()
                WHERE userid = $1
                AND NOW() - created_at >= INTERVAL '24 hours'
                RETURNING userid, membership
            ),

            balanceupdate AS (
                UPDATE balances
                SET robux = robux + CASE
                    WHEN (
                        SELECT membership
                        FROM updated
                    ) = 'Free' THEN 100

                    WHEN (
                        SELECT membership
                        FROM updated
                    ) = 'Classic' THEN 15

                    WHEN (
                        SELECT membership
                        FROM updated
                    ) = 'Turbo' THEN 35

                    WHEN (
                        SELECT membership
                        FROM updated
                    ) = 'Outrageous' THEN 60

                    ELSE 0
                END
                WHERE userid = $1
                RETURNING robux
            )

            SELECT
                u.friendrequests_count,
                u.trades_count,
                u.messages_count,
                b.robux
            FROM users u
            JOIN balances b ON b.userid = u.id
            WHERE u.id = $1
            """,
            UserId
        )

    await dragonfly.set(
        "AuthData" + str(UserId),
        json.dumps({ 
            "friendcount": data["friendrequests_count"],
            "tradescount": data["trades_count"],
            "messagecount": data["messages_count"],
            "balance": data["robux"]
        }),
        ex = 30
    )

    return {
        "success": True,
        "friendcount": data["friendrequests_count"],
        "tradescount": data["trades_count"],
        "messagecount": data["messages_count"],
        "balance": data["robux"],
    }

@app.get("/api/inventory")
@userlimiter.limit("70/minute")
async def inventory(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]

    return await getInventoryData(UserId)

@app.get("/api/membership")
@userlimiter.limit("70/minute")
async def membership(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    pool = await getpgPool()
    Tier = None
    UserId = CookieData[0]
    dragonfly = await getDragonfly()
    dragonFlyData = await dragonfly.get("Tier" + str(UserId))

    if dragonFlyData:
        return {"tier": dragonFlyData }

    async with pool.acquire() as conn:
        Tier = await conn.fetchval("""
            SELECT membership
            FROM membership
            WHERE userid = $1
        """, CookieData[0])

    await dragonfly.set("Tier" + str(UserId),Tier,ex = 86400)
    return {"tier": Tier }
        
@app.post("/api/register")
@userlimiter.limit("15/minute")
async def register(request : Request,data : RegisterSchema,Session : str = Cookie(None),user_agent : str = Header(None)):
    Username = data.Username
    Password = data.Password
    ConfirmPassword = data.ConfirmPassword
    IP = getUserIP(request)

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
    IPData = await getIPData(IP)
    SessionId = uuid.uuid4()
    UserAgent = user_agent
    City = IPData.get("city")
    Region = IPData.get("region")
    Country = IPData.get("country_name")
    Location = f"{City},{Region},{Country}"

    async with pgPool.acquire() as conn:
        async with conn.transaction():
            UserId = await conn.fetchval("""
                WITH new_user AS (
                    INSERT INTO users (
                        username, password, email,
                        friendrequests_count, messages_count,
                        messages, admin, equipped_items, version
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    RETURNING id
                ),

                balance_insert AS (
                    INSERT INTO balances (userid, robux)
                    SELECT id, 0 FROM new_user
                ),

                trades_insert AS (
                    INSERT INTO trades (userid, inbound_trades, outbound_trades, inactive_trades, completed_trades)
                    SELECT id, '[]', '[]', '[]', '[]' FROM new_user
                ),

                inventory_insert AS (
                    INSERT INTO inventory (userid, items)
                    SELECT id, '[]' FROM new_user
                ),

                membership_insert AS (
                    INSERT INTO membership (userid, membership, created_at)
                    SELECT id, 'Free', NOW() FROM new_user
                ),

                friendrequests_insert AS (
                    INSERT INTO friendrequests (userid, requests)
                    SELECT id, '[]' FROM new_user
                ),

                friends_insert AS (
                    INSERT INTO friends (userid, friends)
                    SELECT id, '[]' FROM new_user
                ),

                followers_insert AS (
                    INSERT INTO followers (userid, followers)
                    SELECT id, '[]' FROM new_user
                ),
                                         
                user_sessions_insert AS (
                    INSERT INTO user_sessions (id, userid, expires_at, location, user_agent)
                    SELECT $10, id, NOW() + INTERVAL '365 days', $11, $12
                    FROM new_user
                ),
                
                followings_insert AS (
                    INSERT INTO followings (userid, followings)
                    SELECT id, '[]' FROM new_user
                )

                SELECT id FROM new_user;
            """,
            Username,
            PasswordHash,
            "",
            0,
            0,
            json.dumps([]),
            False,
            json.dumps([]),
            "1",
            SessionId,
            Location,
            UserAgent
            )

            if UserId is None:
                return {"success":False,"message": "Something went wrong registering, please try again later."}
            else:
                return setUserSession(serializer,UserId,Username)

@app.post("/api/login")
@userlimiter.limit("15/minute")
async def login(request : Request,data : LoginSchema, Session : str = Cookie(None),user_agent : str = Header(None)):
    Username = data.Username
    Password = data.Password
    IP = getUserIP(request)

    if Session:
        return {"success":False,"message": "Please log out before attempting to log in."}

    pgPool = await getpgPool()

    async with pgPool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(""" 
                SELECT id, username, password, email
                FROM users
                WHERE username = $1                  
            """, Username)

            if user is None:
                return {"success":False,"message": "Invalid username or password."}

            if not argon2Verify(user["password"],Password):
                return {"success":False,"message": "Invalid username or password."}
            
            IPData = await getIPData(IP)
            SessionId = uuid.uuid4()
            UserAgent = user_agent
            City = IPData.get("city")
            Region = IPData.get("region")
            Country = IPData.get("country_name")
            Location = f"{City},{Region},{Country}"

            await conn.execute("""
                INSERT INTO user_sessions (id, userid, expires_at, location, user_agent)
                VALUES ($1, $2, NOW() + INTERVAL '365 days', $3, $4)
            """, SessionId, user["id"], Location, UserAgent)

            return setUserSession(serializer,user["id"],Username)
    
@app.post("/api/messages/action")
@userlimiter.limit("70/minute")
async def messagesaction(request : Request,data : MessagesActionSchema,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    if len(data.ids) > 10:
        return {"success":False,"message": "Too many operations!"}

    UserId = UserData[0]
    Version = UserData[1]
    Action = data.action.lower()

    FieldMap = {
        "read": ("isRead","true"),
        "unread": ("isRead","false"),
        "archive": ("isArchived","true"),
        "unarchive": ("isArchived","false")
    }

    Field,Value = FieldMap.get(Action,("isRead","true"))

    pgPool = await getpgPool()

    async with pgPool.acquire() as conn:
        await conn.execute(
            f"""
            WITH updated_data AS (
                SELECT 
                    id,
                    jsonb_agg(
                        CASE 
                            WHEN (elem->>'id') = ANY($1) THEN 
                                jsonb_set(elem, '{{{Field}}}', to_jsonb($4))
                            ELSE elem
                        END
                    ) AS new_messages
                FROM users, jsonb_array_elements(messages) AS elem
                WHERE id = $2
                GROUP BY id
            )
            UPDATE users
            SET 
                messages = updated_data.new_messages,
                messages_count = (
                    SELECT COUNT(*) 
                    FROM jsonb_array_elements(updated_data.new_messages) AS e 
                    WHERE e->>'isRead' = 'false'
                )
            FROM updated_data
            WHERE users.id = updated_data.id 
            AND users.id = $2 
            AND users.version = $3;
            """,
            data.ids, 
            UserId,   
            Version, 
            Value     
        )

    return {"success":True}

@app.post("/api/sendmessage", dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def sendmessage(request : Request,data : SendMessageSchema,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    InputMessage = data.msg
    MessageId = data.id
    MessageSubject = data.subject
    UserId = data.userid

    if InputMessage and MessageId and MessageSubject and UserId:
        SendUserId = UserData[0]
        Message = await getSingularMessageById(MessageId,SendUserId)

        if not Message:
            return {"success": False,"message": "Message doesn't exist."}
        
        OriginalMessage = Message["elem"]

        if isinstance(OriginalMessage,str):
            OriginalMessage = json.loads(OriginalMessage)

        ReplyContent = (
            f"{InputMessage}\n\n"
            f"------------------------------\n"
            f"On {OriginalMessage['createdat']}, {OriginalMessage['sender']} wrote:\n"
            f"{OriginalMessage['text']}"
        )

        NewMessageSubject = OriginalMessage["subject"]
        SendUserName = await getUsernameByUserId(SendUserId)

        if not SendUserName:
            return {"success":False,"message": "User doesn't exist."}

        await NewMessage(
            IsSystem = False,
            IsNotification = False,
            Subject = NewMessageSubject,
            SenderUserName = SendUserName,
            previewText = ReplyContent[:25],
            text = ReplyContent,
            RecieverUserId = UserId,
            SendAvatarUrl = "https://cartii.fit//images/thumbnails/4bc91594228677dc7d11a1c7fe16a693da8d42f90b42c219a24d15917924e285_thumbnail.png",
            Reply = True,
            SenderUserId = SendUserId
        )

        return {"success":True}

    if InputMessage and MessageSubject and UserId:
        SendUserId = UserData[0]
        SendUserName = await getUsernameByUserId(SendUserId)

        if not SendUserName:
            return {"success":False,"message": "User doesn't exist."}

        await NewMessage(
            IsSystem = False,
            IsNotification = False,
            Subject = MessageSubject,
            SenderUserName = SendUserName,
            previewText = InputMessage[:25],
            text = InputMessage,
            RecieverUserId = UserId,
            SendAvatarUrl = "https://cartii.fit//images/thumbnails/4bc91594228677dc7d11a1c7fe16a693da8d42f90b42c219a24d15917924e285_thumbnail.png",
            SenderUserId = SendUserId
        )

    return {"success":True}

@app.post("/api/membership/upgrade",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changemembership(request : Request,data : MemberShipChangeSchema,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    Version = UserData[1]

    if data.tier not in ["Free","Classic","Turbo","Outrageous"]:
        return {"success":False,"message": "Invalid Membership type."}

    if data.tier != "Outrageous":
        pool = await getpgPool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE membership
                SET membership = $1
                FROM users
                WHERE membership.userid = $2 
                AND users.id = $2 
                AND users.version = $3;
                """,
                data.tier,    
                UserData[0],  
                str(Version)       
            )

            if result == "UPDATE 0":
                raise HTTPException(status_code = 403, detail = "Invalid session")

        dragonfly = await getDragonfly()
        await dragonfly.set("Tier" + str(UserId),data.tier,ex = 86400)
        return {"success": True,"tier": data.tier }
    else:
        pool = await getpgPool()
        async with pool.acquire() as conn:
            Tier = await conn.fetchval("""
                SELECT membership
                FROM membership
                WHERE userid = $1
            """, UserId)

        return {"success": False,"tier": Tier,"message": "Upgrading to Outrageous is currently not available." }

@app.post("/api/logoutallsessions",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def logoutall(request : Request,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    Version = UserData[1]

    pool = await getpgPool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute("""
                UPDATE users
                SET version = (version::INTEGER + 1)::TEXT
                WHERE userid = $1 AND version = $2
            """, UserId,str(Version))

            if result == "UPDATE 0":
                raise HTTPException(status_code = 403, detail = "Invalid session")
            
            await conn.execute("""
                DELETE FROM user_sessions
                WHERE userid = $1     
            """,UserId)
            
    response = JSONResponse(status_code = 200, content = {"success":True})
    response = await clearCookies(response)
    return response
