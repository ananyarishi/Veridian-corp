from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

Action = Literal["Auto-Resolve", "Route to Team", "Flag for Review"]

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)

class NewRequest(BaseModel):
    employee: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=200)
    message: str = Field(min_length=10, max_length=5000)

class ReviewRequest(BaseModel):
    decision: Action
    note: str = ""
    assigned_team: Optional[str] = None

class AnalyzeRequest(BaseModel):
    force: bool = False

class CommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)

class PolicyCreate(BaseModel):
    id: str
    title: str
    category: str
    desc: str
    body: str
