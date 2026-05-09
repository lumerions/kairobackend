from pydantic import BaseModel,Field

class RegisterSchema(BaseModel):
    Username : str
    Password : str
    ConfirmPassword: str = Field(alias="Confirm Password")

class LoginSchema(BaseModel):
    Username : str
    Password : str
