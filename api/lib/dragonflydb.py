import redis.asyncio as aioredis

async def getDragonfly():
    dragonFly = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
    return dragonFly

