from fastapi import Request,FastAPI
from lib.functions import getSessionKey
from slowapi import Limiter
from lib.serializer import serializer

async def LimiterKey(request: Request):
    return await getSessionKey(request, serializer)

userlimiter = Limiter(
    key_func = LimiterKey
)

app = FastAPI()
