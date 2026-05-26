from getPostgresConn import *
import asyncio
import json

ForumData = [
    {
        "id": "1",
        "name": "General",
        "description": "General forum"
    },
    {
        "id": "2",
        "name": "Trading",
        "description": "Trade talk"
    }
]


ForumNames = {
    1: "Main",
    2: "Trades"
}

async def createForums():
    pool = await getpgPool()
    async with pool.acquire() as conn:
        for i, forum in enumerate(ForumData, start = 1):
            forum["id"] = str(i)
            await conn.execute("""
                INSERT INTO forums (title, forums)
                VALUES ($1, $2::jsonb)
            """, ForumNames[i], json.dumps([forum]))

asyncio.run(createForums())