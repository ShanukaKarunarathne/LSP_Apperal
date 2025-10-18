from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class AccessLevel(str, Enum):
    LEVEL_1 = "read_write"
    LEVEL_2 = "full_access"

class UserBase(BaseModel):
    username: str
    access_level: AccessLevel

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None