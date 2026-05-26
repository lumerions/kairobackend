

from fastapi import APIRouter,Request,Cookie,Depends
import json
from routes.shared.shared import userlimiter
from lib.getPostgresConn import *
from middleware.authMiddleware import sessionValid
from middleware.csrfMiddleware import CheckCSRFToken
from lib.functions import returnSerializedCookieData
from lib.serializer import serializer
from lib.messages import *
from lib.schemas import MessagesActionSchema
from lib.functions import getUserIdByUsername
from math import ceil

router = APIRouter(
    prefix="/api/messages",
    tags=["messages"]
)

@router.post("/action",dependencies=[Depends(sessionValid), Depends(CheckCSRFToken)])
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


@router.get("",dependencies = [Depends(sessionValid)])
@userlimiter.limit("70/minute")
async def messages(request : Request,Session : str = Cookie(None),tab : str = "Inbox",page : int = 1):
    CookieData = returnSerializedCookieData(Session,serializer)

    if isinstance(CookieData,bool):
        return {"success":False,"message": "Error with validating session."}

    UserId = CookieData[0]
    Limit = 10
    offset = (page - 1) * Limit
    Messages, TotalItemCount = await getMessagesByType(UserId, offset, tab)
    TotalPageCount = ceil(TotalItemCount / Limit) if TotalItemCount else 1
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
        "totalPages": TotalPageCount if TotalPageCount else 1,
    }


@router.get("/details",dependencies=[Depends(sessionValid)])
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
        
        MessageData = Message["elem"]
 
        if isinstance(MessageData, str):
            MessageData = json.loads(MessageData)

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
