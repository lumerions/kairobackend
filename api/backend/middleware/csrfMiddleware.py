
from fastapi import Request,Cookie,HTTPException,Header
from itsdangerous import BadSignature,SignatureExpired
from lib.getPostgresConn import *
from lib.serializer import serializer
import secrets

def generateNewCsrf(UserId : int):
    CSRFToken = secrets.token_urlsafe(16)
    CookieValue = serializer.dumps({
        "csrf": CSRFToken,
        "userId": UserId,
        "version": "1"
    })

    return CookieValue

def setCsrf(response,UserId : int):
    response.set_cookie(
        key = "csrf",
        value = generateNewCsrf(UserId),
        max_age = 604800,
        httponly = False, 
        samesite = "strict",
        path = "/"
    )

async def CheckCSRFToken(request: Request,x_csrf_token: str = Header(None), csrf: str = Cookie(None), Session : str = Cookie(None)):
    UserId = 0

    try:
        if not csrf:
            raise ValueError("No CSRF cookie")

        serializedSessionData = serializer.loads(Session)
        serializedCSRFData = serializer.loads(csrf)
        UserId = int(serializedSessionData.get("userId"))
        CsrfToken = serializedCSRFData.get("csrf")
        CsrfUserId = serializedCSRFData.get("userId")

        if not x_csrf_token or x_csrf_token != CsrfToken or UserId != CsrfUserId:
            raise ValueError("Validation mismatch")
    
    except (BadSignature,SignatureExpired,ValueError,TypeError):    
        CSRFToken = generateNewCsrf(UserId)
        CookieHeader = f"csrf={CSRFToken}; Max-Age=604800; Path=/; SameSite=Strict; HttpOnly"
        raise HTTPException(
            status_code = 403,
            detail = "Token Validation Error.",
            headers = {
                "Set-Cookie":CookieHeader
            }
        )

    return True
