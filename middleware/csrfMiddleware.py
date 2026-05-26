
from fastapi import Request,Cookie,HTTPException,Header
import secrets

def setCsrf(response,UserId : int):
    response.set_cookie(
        key = "csrf",
        value = secrets.token_urlsafe(32),
        max_age = 604800,
        httponly = False, 
        secure = True,
        samesite = "Strict",
        path = "/"
    )

async def CheckCSRFToken(request: Request,x_csrf_token: str = Header(None), csrf: str = Cookie(None)):
    try:
        if not csrf:
            raise ValueError("No CSRF cookie")
        
        if not x_csrf_token:
            raise ValueError("No csrf sent")
        
        print(x_csrf_token)
        print(csrf)
        
        if not secrets.compare_digest(x_csrf_token, csrf):
            raise ValueError("Validation mismatch")
    
    except ValueError as e:    
        print(e)
        CSRFToken = secrets.token_urlsafe(32)
        CookieHeader = (
        f"csrf={CSRFToken}; Max-Age=604800; "
            f"Path=/; SameSite=Strict; Secure"
        )
        raise HTTPException(
            status_code = 401,
            detail = "Token Validation Error.",
            headers = {
                "Set-Cookie":CookieHeader
            }
        )

    return True