from pydantic import BaseModel,Field
from typing import Optional

class RegisterSchema(BaseModel):
    Username : str
    Password : str
    ConfirmPassword: str = Field(alias="Confirm Password")

class LoginSchema(BaseModel):
    Username : str
    Password : str

class MessagesActionSchema(BaseModel):
    action : str
    ids: list

class MemberShipChangeSchema(BaseModel):
    tier : str

class SendMessageSchema(BaseModel):
    msg: str
    subject: str
    userid: int
    id: Optional[str] = None
