import asyncpg
pgPool = None

async def getpgPool(): 
    global pgPool

    if pgPool is None:
        pgPool = await asyncpg.create_pool(
            user="Main",
            password="essees",
            database="Main",
            host="127.0.0.1",
            min_size=5,
            max_size=20
        )

    return pgPool

