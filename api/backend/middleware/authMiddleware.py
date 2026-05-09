from fastapi import Request,Cookie,HTTPException
from itsdangerous import BadSignature,SignatureExpired
from lib.getPostgresConn import *
from lib.serializer import serializer

async def sessionValid(
    request: Request, 
    Session: str = Cookie(None)
):
    try:

        if not Session:
            raise HTTPException(status_code = 401, detail = " No Session valid")

        serializedData = serializer.loads(Session)
        
        try:
            UserId = int(serializedData.get("userId"))
            Version = int(serializedData.get("version"))
        except (ValueError,TypeError):
            raise HTTPException(status_code = 401, detail = "Error getting session")
        
        if not UserId or not Version:
            raise HTTPException(status_code = 401, detail = "Invalid session")
        
        pool = await getpgPool()
        async with pool.acquire() as conn:
            DBVersion = await conn.fetchval(
                "SELECT version FROM users WHERE id = $1",
                UserId
            )

            if int(DBVersion) != Version:
                raise HTTPException(status_code = 401, detail = "Session expired")

        return True
    except (BadSignature,SignatureExpired,ValueError,TypeError):
        raise HTTPException(status_code = 401, detail = "Invalid session")
