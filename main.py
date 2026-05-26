from fastapi import Request,Cookie,Depends,Header
from fastapi.responses import JSONResponse
from lib.schemas import *
from lib.functions import *
from lib.getPostgresConn import *
from lib.serializer import serializer
from config.Config import *
from lib.messages import *
from lib.emails import *
from lib.connections import *
from lib.forums import *
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from middleware.authMiddleware import sessionValid
from middleware.csrfMiddleware import CheckCSRFToken,setCsrf
from routes.shared.shared import userlimiter,app
from routes.forums import router as forums_router
from routes.messages import router as messages_router
from routes.threads import router as threads_router
from routes.groups import router as groups_router
import json,pyotp,uuid,resend
from math import ceil

config = Config()
resend.api_key = config.resendkey

app.include_router(forums_router)
app.include_router(messages_router)
app.include_router(threads_router)
app.include_router(groups_router)
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
    if exc.status_code == 403:
        response = JSONResponse(status_code = exc.status_code, content = {"success":False,"message": exc.detail})
        response = clearCookies(response)
        return response
    if exc.status_code == 401:
        response = JSONResponse(status_code = exc.status_code, content = {"success":False,"message": exc.detail},headers = exc.headers)
        return response
    
    
@app.get("/api/connections",dependencies = [Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def connections(request : Request,Session : str = Cookie(None),tab : str = "Requests",page : int = 1):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]
    Limit = 10
    offset = (page - 1) * Limit
    ConnectionData, TotalItemCount = await GetConnectionByType(tab, offset, UserId)
    TotalPageCount = ceil(TotalItemCount / Limit) if TotalItemCount else 1
    FormattedData = []

    """
    for item in ConnectionData:
        print(item)
        print(type(item), item)

        Entry = item.get("elem",None)

        if isinstance(Entry,str):
            Entry = json.loads(Entry)

        FormattedData.append(Entry)
    """ 

    return {
        "success":True,
        "data": FormattedData,
        "counts": {
            "Requests": 2,
            "Friends": 54,
            "Followers": 120,
            "Followings": 45
        },
        "currentPage": page,
        "totalPages": (TotalPageCount + 10 - 1) if TotalPageCount else 1,
    }

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
                    ) = 'Free' THEN 0

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

@app.get("/api/settings")
@userlimiter.limit("70/minute")
async def settings(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    await sessionValid(request,Session)

    UserId = CookieData[0]

    dragonfly = await getDragonfly()
    dragonFlyData = await dragonfly.get("SD" + str(UserId))

    if dragonFlyData:
        AuthData = json.loads(dragonFlyData)
        AuthData["success"] = True
        return AuthData

    pool = await getpgPool()
    async with pool.acquire() as conn:
        data = await conn.fetchrow("""
            SELECT 
                u.username,
                p.email,
                p.message_status,
                p.vip_server_status,
                p.follow_status,
                p.inventory_status,
                p.trade_status
            FROM users u
            JOIN additional_user_data p ON p.userid = u.id
            WHERE u.id = $1
        """, UserId)

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

    return {
        "success": True,
        "email": data["email"],
        "username": data["username"],
        "message_status": data["message_status"],
        "vip_server_status": data["vip_server_status"],
        "follow_status": data["follow_status"],
        "inventory_status": data["inventory_status"],
        "trade_status": data["trade_status"]
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

@app.get("/api/authenticationdata")
@userlimiter.limit("70/minute")
async def authenticationdata(request : Request,Session : str = Cookie(None)):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = CookieData[0]
    pool = await getpgPool()

    async with pool.acquire() as conn:
        data = await conn.fetchrow("""
            SELECT 
                u.twofa_enabled,
                aud.email
            FROM users u
            JOIN additional_user_data aud
                ON aud.userid = u.id
            WHERE u.id = $1
        """, UserId)

        if not data:
            return {"success": False}

        return {"success": True,"emailVerified": len(data["email"]) > 0,"twoFactorEnabled":data["twofa_enabled"]}

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
    
    if Username == Password:
        return {"success":False,"message": "Password can't be the same as the username."}

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
            UpdatedRow = await conn.fetchrow("""
                WITH new_user AS (
                    INSERT INTO users (
                        username, password,
                        friendrequests_count, messages_count,
                        messages, admin, version
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    RETURNING id, version
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
                               
                additional_insert AS (
                    INSERT INTO additional_user_data (userid)
                    SELECT id FROM new_user
                ),
                                         
                user_sessions_insert AS (
                    INSERT INTO user_sessions (id, userid, expires_at, location, user_agent)
                    SELECT $8, id, NOW() + INTERVAL '365 days', $9, $10
                    FROM new_user
                )
                                     
                SELECT id, version FROM new_user;
            """,
            Username,
            PasswordHash,
            0,
            0,
            json.dumps([]),
            False,
            "1",
            SessionId,
            Location,
            UserAgent
            )

            UserId = UpdatedRow["id"]
            Version = UpdatedRow["version"]

            return setUserSession(serializer,UserId,Username,int(Version))
        
    return {"success":False,"message": "Something went wrong registering, please try again later."}


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
                SELECT id, username, password,version,twofa_enabled
                FROM users
                WHERE username = $1                  
            """, Username)

            if user is None:
                return {"success":False,"message": "Invalid username or password."}

            if not argon2Verify(user["password"],Password):
                return {"success":False,"message": "Invalid username or password."}
            
            if user["twofa_enabled"]:
                return {"success":True,"twofa": True}
            
            IPData = await getIPData(IP)
            print(IPData)
            SessionId = uuid.uuid4()
            UserAgent = user_agent
            City = IPData.get("city")
            Region = IPData.get("region")
            Country = IPData.get("country_name")
            Location = f"{City},{Region},{Country}"
            Version = user["version"]

            await conn.execute("""
                INSERT INTO user_sessions (id, userid, expires_at, location, user_agent)
                VALUES ($1, $2, NOW() + INTERVAL '365 days', $3, $4)
            """, SessionId, user["id"], Location, UserAgent)

            usersessionResponse = setUserSession(serializer,user["id"],Username,int(Version))
            setCsrf(usersessionResponse,user["id"])
            return usersessionResponse
    

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
            result = await conn.fetchval("""
                WITH updated AS (
                    UPDATE users
                    SET version = (version::INTEGER + 1)::TEXT
                    WHERE id = $1 AND version = $2
                    RETURNING id
                ),
                deleted AS (
                    DELETE FROM user_sessions
                    WHERE userid = $1
                    AND EXISTS (SELECT 1 FROM updated)
                    RETURNING 1
                )
                SELECT EXISTS (SELECT 1 FROM updated);
            """, UserId, str(Version))

            if not result:
                raise HTTPException(status_code = 403, detail = "Invalid session")

    response = JSONResponse(status_code = 200, content = {"success":True})
    response = clearCookies(response)
    return response

@app.post("/api/changeusername",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changeuser(request : Request,data : NewUsernameSchema,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    Version = UserData[1]
    NewUserName = data.newUsername
    Password = data.password

    if (len(Password) < 8):
        return {"success":False,"message": "Password must be atleast 8 characters."}

    if not UserNameValid(NewUserName):
        return {"success":False,"message": "Usernames can only have 3 to 20 characters, consisting of numbers, letters, and up to one underscore."}

    pool = await getpgPool()
    NewSettingsData = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow("""
                SELECT u.password, b.robux
                FROM users u
                JOIN balances b ON b.userid = u.id
                WHERE u.id = $1 AND u.version = $2
            """, UserId, Version)

            if user is None:
                return {"success":False,"message": "Invalid username or password."}
            
            Robux = user["robux"]

            if Robux < 1000:
                return {"success":False,"message": "Insufficient funds."}

            if not argon2Verify(user["password"],Password):
                return {"success":False,"message": "Invalid username or password."}
            
            try:
                NewSettingsData = await conn.fetchrow("""
                    UPDATE users u
                    SET username = $1
                    FROM balances b
                    WHERE u.id = $2
                    AND u.version = $3
                    AND b.userid = u.id
                    AND b.robux >= 1000
                    RETURNING
                        u.email,
                        u.username,
                        u.message_status,
                        u.vip_server_status,
                        u.follow_status,
                        u.inventory_status,
                        u.trade_status,
                        b.robux - 1000 AS new_robux
                """, NewUserName, UserId, str(Version))
            except (asyncpg.UniqueViolationError):
                return {"success":False,"message": "Username already taken."}

    await setSettingsData(NewSettingsData,UserId)  
    return {"success":True}

@app.post("/api/privacy-settings",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def privacyoption(request : Request,data : SettingsSchema,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    Version = UserData[1]
    setting = data.setting.strip().lower()
    value = data.value.strip()

    if setting not in ["messages","invites","follow","inventory","trade"]:
        return {"success":False,"message": "Invalid setting input."}
    
    if value not in ["All Users","No One","Friends","Friends, and Users I Follow","Friends, Users I follow, and Followers"]:
        return {"success":False,"message": "Invalid value input."}
    
    fieldNames = {
        "messages": "message_status",
        "invites": "vip_server_status",
        "follow": "follow_status",
        "inventory": "inventory_status",
        "trade": "trade_status"
    }

    pool = await getpgPool()
    async with pool.acquire() as conn:
        UpdatedRow = await conn.fetchrow(f"""
            UPDATE additional_user_data a
            SET {fieldNames[setting]} = $1
            FROM users u
            WHERE a.userid = $2
            AND u.id = a.userid
            AND u.version = $3
            RETURNING
                u.username,
                a.email,
                a.message_status,
                a.vip_server_status,
                a.follow_status,
                a.inventory_status,
                a.trade_status
        """, value, UserId, str(Version))

        await setSettingsData(UpdatedRow,UserId)  

    return {"success":True}

@app.post("/api/logout",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def logout(request : Request,Session : str = Cookie(None)):
    response = JSONResponse(status_code = 200, content = {"success":True})
    clearCookies(response)
    return response

@app.post("/api/changeaccountemail",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changeaccountemail(request : Request,data : changeAccountEmailSchema,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    Version = UserData[1]
    UserName = UserData[2]
    email = data.email
    pool = await getpgPool()

    if not await checkUserEmailLimit(UserName):
        return {"success":False,"message": "Email send ratelimited, please try again later."}

    EmailCode = secrets.token_hex(5)

    async with pool.acquire() as conn:
        result = await conn.execute(""" 
            UPDATE additional_user_data AS aud
            SET 
                pending_email = $1,
                email_code = $2,
                email_code_expiration = NOW()
            FROM users AS u
            WHERE 
                u.username = $3
                AND u.version = $4
                AND aud.userid = u.id
        """, email, EmailCode, UserName, str(Version))

        if result == "UPDATE 0":
            return {"success":False,"message": "This session is invalid."}
        
    EmailContent = emailHtml(
        code = EmailCode,
        title = "Email Verification",
        message = "Use the code below to verify your email address:"
    )

    await sendEmail("Email Verification <verification@syntaxrevival.store>",EmailCode,"Email Verification",EmailContent)

    return {"success":True}

@app.post("/api/verifyemail",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def verifyemail(request : Request,data : verifyAccountEmail,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    Version = UserData[1]
    UserName = UserData[2]
    code = data.code.strip()
    pool = await getpgPool()
    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE additional_user_data a
            SET 
                email = a.pending_email,
                pending_email = NULL,
                email_code = NULL,
                email_code_expiration = NULL
            FROM users u
            WHERE 
                u.id = a.userid
                AND u.username = $1
                AND u.version = $2
                AND a.email_code = $3
                AND a.email_code IS NOT NULL
                AND a.email_code != 'None'
                AND a.email_code_expiration IS NOT NULL
                AND a.email_code_expiration > NOW() - INTERVAL '15 minutes'
        """, UserName, str(Version), code)

        if result == "UPDATE 0":
            return {"success":False,"message": "Invalid or expired verify code."}

    return {"success":True}

@app.post("/api/verify-2fa")
@userlimiter.limit("70/minute")
async def verify2facode(request : Request,data : Verify2faSchema,Session : str = Cookie(None),user_agent : str = Header(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    Version = UserData[1]
    username = data.username
    code = data.code
    IP = getUserIP(request)
    pgPool = await getpgPool()

    async with pgPool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(""" 
                SELECT twofa_secret,version,id
                FROM users
                WHERE username = $1 AND version = $2               
            """, username,Version)

            if user is None:
                return {"success":False,"message": "Invalid username."}

            totp = pyotp.TOTP(user["twofa_secret"])

            if not totp.verify(code):
                return  {"success":False,"message": "Invalid code."}
            
            IPData = await getIPData(IP)
            print(IPData)
            SessionId = uuid.uuid4()
            UserAgent = user_agent
            City = IPData.get("city")
            Region = IPData.get("region")
            Country = IPData.get("country_name")
            Location = f"{City},{Region},{Country}"
            Version = user["version"]

            await conn.execute("""
                INSERT INTO user_sessions (id, userid, expires_at, location, user_agent)
                VALUES ($1, $2, NOW() + INTERVAL '365 days', $3, $4)
            """, SessionId, user["id"], Location, UserAgent)

    usersessionResponse = setUserSession(serializer,user["id"],username,int(Version))
    setCsrf(usersessionResponse,user["id"])
    return usersessionResponse

@app.post("/api/enable-2fa",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def enable2fa(request : Request,Session : str = Cookie(None),user_agent : str = Header(None)):
    pool = await getpgPool()
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    Secret = pyotp.random_base32()
    UserName = UserData[2]

    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE users u
            SET twofa_secret = $1
            FROM additional_user_data aud
            WHERE u.id = aud.userid
            AND u.id = $2
            AND COALESCE(aud.email, '') <> ''
            AND COALESCE(u.twofa_enabled, FALSE) = FALSE
            RETURNING u.id
        """, Secret, UserId)

        if result == "UPDATE 0":
            return {"success":False,"message": "Email missing or 2fa already enabled."}
        
    totp = pyotp.TOTP(Secret)
    OtpUrl = totp.provisioning_uri(
        name = UserName,
        issuer_name = "Kairo"
    )

    return {"success":True,"url": OtpUrl,"secret": Secret}

@app.post("/api/change2fastatus",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def change2fastatus(request : Request,data : change2fastatus,Session : str = Cookie(None),user_agent : str = Header(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    Version = UserData[1]
    Code = data.code
    Status = data.status

    if not isinstance(Status,bool):
        return {"success":False,"message": "Status must be a boolean."}
    
    pool = await getpgPool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(""" 
            SELECT twofa_secret
            FROM users
            WHERE id = $1 AND version = $2               
        """, UserId,Version)

        if user is None:
            return {"success":False,"message": "Invalid username."}
        
        Secret = user["twofa_secret"]
        totp = pyotp.TOTP(Secret)

        if not totp.verify(Code):
            return  {"success":False,"message": "Invalid code."}

        await conn.execute(f""" 
            UPDATE users
            SET twofa_enabled = {Status}
            WHERE id = $1 AND version = $2               
        """, UserId,Version)

    return {"success":True}

@app.post("/api/changepassword",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def changepassword(request : Request,data : changePassword,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    confirmPassword = data.confirmPassword
    currentPassword = data.currentPassword
    newPassword = data.newPassword

    if len(newPassword) < 8 or len(currentPassword) < 8 or len(confirmPassword) < 8:
        return {"success": False,"message": "New Password or Current Password or Confirm Password must be 8 characters."}

    if confirmPassword != newPassword:
        return {"success": False,"message": "New password and confirm passwords don't match."}

    pool = await getpgPool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(""" 
            SELECT password
            FROM users
            WHERE id = $1                  
        """, UserId)

        if user is None:
            return {"success":False,"message": "Invalid username."}
        
        HashedPassword = user["password"]

        if not argon2Verify(HashedPassword,currentPassword):
            return {"success":False,"message": "Invalid username or password."}
        
        NewPasswordHash = argon2Hash(newPassword)
        UpdatedRow = await conn.fetchrow(""" 
            UPDATE users
            SET password = $2
            WHERE id = $1             
            RETURNING email, username, message_status,vip_server_status,follow_status,inventory_status,trade_status
        """, UserId,NewPasswordHash)

        if not UpdatedRow:
            return {"success":False,"message": "Something went wrong with changing password."}

        await setSettingsData(UpdatedRow,UserId)  

    return {"success":True}

@app.post("/api/update-bio",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def updatebio(request : Request,data : updateBio,Session : str = Cookie(None)):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    Version = UserData[1]
    Bio = data.bio

    pool = await getpgPool()

    async with pool.acquire() as conn:
        UpdatedRow = await conn.fetchrow("""
            WITH user_check AS (
                SELECT id, username
                FROM users
                WHERE id = $1 AND version = $3
            ),
            updated_bio AS (
                UPDATE additional_user_data
                SET bio = $2
                WHERE userid = $1
                AND EXISTS (SELECT 1 FROM user_check)
                RETURNING 
                    vip_server_status, 
                    message_status, 
                    follow_status, 
                    inventory_status, 
                    trade_status, 
                    bio,
                    email
            )
            SELECT 
                u.username,
                b.email,
                b.message_status,
                b.vip_server_status,
                b.follow_status,
                b.inventory_status,
                b.trade_status,
                b.bio
            FROM user_check u
            LEFT JOIN updated_bio b ON true
        """, UserId, Bio, str(Version))

        if not UpdatedRow:
            return {"success":False,"message": "Something went wrong with changing bio."}
                
        await setSettingsData(UpdatedRow,UserId)  

    return {"success":True}

@app.delete("/api/posts/{post_id}/{forum_id}",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def deletepost(request : Request,Session : str = Cookie(None),post_id : str = None,forum_id : str = None):
    try:
        post_id = int(post_id)
        forum_id = int(forum_id)
    except (ValueError,TypeError):
        return {"success":True,"message": "Invalid post data type."}

    pool = await getpgPool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE forums
            SET posts_data = (
                SELECT jsonb_agg(post)
                FROM jsonb_array_elements(posts_data) AS post
                WHERE (post->>'id')::bigint != $2
            )
            WHERE id = $1
        """, forum_id, post_id)

    return {"success":True}
