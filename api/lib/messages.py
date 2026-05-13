from lib.getPostgresConn import *
import secrets
import json
from datetime import datetime,timezone
import asyncio

async def getSingularMessageById(MessageId : str,UserId : int) -> list:
    pool = await getpgPool()

    async with pool.acquire() as conn:
        query = """
            SELECT elem
            FROM users
            CROSS JOIN jsonb_array_elements(messages) AS elem
            WHERE id = $1
            AND elem->>'id' = $2
            LIMIT 1;
        """

        row = await conn.fetchrow(query, UserId, MessageId)

        if not row:
            return None
        
        return row
    
async def getMessagesByType(UserId : int,offset : int,tab : str) -> list:
    pool = await getpgPool()
    msgType = tab.lower()

    async with pool.acquire() as conn:
        query = """
            SELECT 
                elem,
                COUNT(*) OVER() AS total_count
            FROM users
            CROSS JOIN jsonb_array_elements(messages) AS elem
            WHERE id = $1
              AND elem->>'type' = $4
            ORDER BY (elem->>'timestamp')::timestamptz DESC
            LIMIT $2 OFFSET $3;
        """

        rows = await conn.fetch(query, UserId, 10, offset, msgType)
        TotalCount = rows[0]["total_count"] if rows else 0
        return [rows,TotalCount]
    
async def NewMessage(IsSystem : bool = False,IsNotification : bool = False,Subject : str = None,SenderUserName : str = "",previewText : str = "",text : str = "",RecieverUserId : int = 0,SendAvatarUrl : str = "https://revival-list.com/gallery/KryptonIcon2BIG.png",Reply : bool = None,SenderUserId : int = None) -> bool:
    id = secrets.token_urlsafe(16)
    FormattedSubject = None
    
    if Reply:
        FormattedSubject = "RE: " + Subject

    pool = await getpgPool()
    now = datetime.now(timezone.utc)

    RecieverMessage = {
        "id": id,
        "isRead": False,
        "sender": SenderUserName,
        "subject": FormattedSubject or Subject,
        "isSystem": IsSystem,
        "isArchived": False,
        "previewText": previewText,
        "text": text,
        "senderAvatar": SendAvatarUrl,
        "type": "inbox",
        "message": text,
        "timestamp": now.isoformat(),
        "createdat": now.strftime("%d/%m/%Y at %H:%M")
    }

    SenderSentMessage = RecieverMessage.copy()
    SenderSentMessage["type"] = "sent"
    SenderSentMessage["isRead"] = True

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET
                messages = messages || (
                    CASE
                        WHEN id = $1 THEN $3::jsonb
                        WHEN id = $2 THEN $4::jsonb
                    END
                ),
                messages_count = CASE
                    WHEN id = $1 THEN messages_count + 1
                    ELSE messages_count
                END
            WHERE id IN ($1, $2)
            """,
            RecieverUserId,
            SenderUserId,
            json.dumps([RecieverMessage]),
            json.dumps([SenderSentMessage])
        )

    return True

async def testInsert():
    await NewMessage(
        IsSystem = True,
        IsNotification = True,
        Subject = "hi",
        SenderUserName = "dogman1234",
        previewText = "inquiry",
        text = "important stuff",
        RecieverUserId = 15,
        SendAvatarUrl = "https://cartii.fit//images/thumbnails/4bc91594228677dc7d11a1c7fe16a693da8d42f90b42c219a24d15917924e285_thumbnail.png"
    )


if __name__ == "__main__":
    asyncio.run(testInsert())
