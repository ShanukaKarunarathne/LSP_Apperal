from pydantic import BaseModel, Field
from typing import Optional

class User(BaseModel):
    username: str
    email: str
    access_level: int = Field(..., description="1 for read-only, 2 for full access")

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    access_level: int

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None