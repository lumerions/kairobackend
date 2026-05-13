from fastapi import Request,Cookie,HTTPException
from itsdangerous import BadSignature,SignatureExpired
from lib.getPostgresConn import *
from lib.serializer import serializer
from typing import Optional
from lib.dragonflydb import *

async def sessionValid(request: Request, Session: str = Cookie(None)) -> Optional[bool]:
    try:

        if not Session:
            raise HTTPException(status_code = 401, detail = "No Session valid")

        serializedData = serializer.loads(Session)
        
        try:
            UserId = int(serializedData.get("userId"))
            Version = int(serializedData.get("version"))
        except (ValueError,TypeError):
            raise HTTPException(status_code = 401, detail = "Error getting session")
        
        if not UserId or not Version:
            raise HTTPException(status_code = 401, detail = "Invalid session")
        
        dragonfly = await getDragonfly()
        dragonFlyVersion = await dragonfly.get("V" + str(UserId))
        DBVersion = None

        if not dragonFlyVersion:
            pool = await getpgPool()
            async with pool.acquire() as conn:
                DBVersion = await conn.fetchval(
                    "SELECT version FROM users WHERE id = $1",
                    UserId
                )

                if int(DBVersion) != int(Version):
                    raise HTTPException(status_code = 401, detail = "Session expired")
                
                await dragonfly.set("V" + str(UserId),DBVersion)
        else:
            if int(dragonFlyVersion) != int(Version):
                raise HTTPException(status_code = 401, detail = "Session expired")
                
        return [UserId,DBVersion or dragonFlyVersion]
    except (BadSignature,SignatureExpired,ValueError,TypeError):
        raise HTTPException(status_code = 403, detail = "Invalid session")
