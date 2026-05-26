from pydantic import BaseModel,Field,EmailStr
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

class NewUsernameSchema(BaseModel):
    newUsername: str
    password: str

class SettingsSchema(BaseModel):
    setting: str
    value: str

class Verify2faSchema(BaseModel):
    username: str
    code: str

class change2fastatus(BaseModel):
    code: str
    status : bool

class changeAccountEmailSchema(BaseModel):
    email: EmailStr

class verifyAccountEmail(BaseModel):
    code: str

class changePassword(BaseModel):
    confirmPassword: str
    currentPassword: str
    newPassword: str

class updateBio(BaseModel):
    bio : str

class threadReply(BaseModel):
    content : str

class threadCreate(BaseModel):
    content : str
    title : str

class groupCreate(BaseModel):
    name : str
    description : str

class groupDescription(BaseModel):
    groupid : int
    description : str

class groupName(BaseModel):
    groupid : int
    name : str

class groupShout(BaseModel):
    shout : str
    groupid : int

class groupJoin(BaseModel):
    groupid : int

class groupChangeOwner(BaseModel):
    groupid : int
    newgroupownerusername : str

class groupFunds(BaseModel):
    groupid : int
    recieverusername : str
    amount : int

class groupSettings(BaseModel):
    groupid : int
    type : str
    newoption: bool