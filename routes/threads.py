

from fastapi import APIRouter,Request,Cookie,Depends
from routes.shared.shared import userlimiter
from middleware.csrfMiddleware import CheckCSRFToken
from lib.functions import returnSerializedCookieData
from lib.serializer import serializer
from lib.forums import *
from lib.schemas import threadCreate,threadReply

router = APIRouter(
    prefix="/api/threads",
    tags=["threads"]
)

@router.post("/{thread_id}/reply/{forum_id}",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def forumsreply(request : Request,data : threadReply,Session : str = Cookie(None),thread_id : str = None,forum_id : str = None):
    messageContent = data.content.strip()

    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
        
    UserId = UserData[0]
    UserName = UserData[2]
    await ForumPost(UserName,messageContent,thread_id,forum_id,UserId)
    return {"success":True}

@router.post("/createthread/{forum_id}",dependencies = [Depends(CheckCSRFToken)])
@userlimiter.limit("70/minute")
async def createthread(request : Request,data : threadCreate,Session : str = Cookie(None),forum_id : str = None):
    UserData = returnSerializedCookieData(Session,serializer)

    if isinstance(UserData,bool):
        return {"success":False,"message": "Error with validating session."}
    
    UserId = UserData[0]
    UserName = UserData[2]
    messageContent = data.content.strip()
    messageTitle = data.title.strip()

    await NewThread(messageContent,UserName,forum_id,messageTitle,UserId)
    return {"success":True}