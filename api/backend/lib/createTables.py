from getPostgresConn import *
import asyncio

async def CreateTables():
    pool = await getpgPool()
    async with pool.acquire() as conn:
        with open(r"","r") as f: 
            sql = f.read()
            await conn.execute(sql)


asyncio.run(CreateTables())