"""Pydantic models and Mongo helpers for CodeGanak."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Literal
import uuid

from pydantic import BaseModel, Field, EmailStr, ConfigDict


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------- User ----------

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    email: EmailStr
    name: str
    password_hash: str
    created_at: str = Field(default_factory=now_iso)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    created_at: str


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)
    name: str = Field(min_length=1, max_length=100)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------- Repository ----------

RepoStatus = Literal["queued", "cloning", "parsing", "indexing", "ready", "failed"]


class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    user_id: str
    name: str
    source: Literal["zip", "github"]
    github_url: Optional[str] = None
    status: RepoStatus = "queued"
    error: Optional[str] = None
    languages: dict = Field(default_factory=dict)          # {"python": 45, "js": 12}
    primary_language: Optional[str] = None
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    file_count: int = 0
    function_count: int = 0
    class_count: int = 0
    api_count: int = 0
    total_bytes: int = 0
    root_path: Optional[str] = None                        # absolute path on disk
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class RepositoryPublic(BaseModel):
    id: str
    name: str
    source: str
    github_url: Optional[str] = None
    status: str
    error: Optional[str] = None
    languages: dict
    primary_language: Optional[str] = None
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    file_count: int
    function_count: int
    class_count: int
    api_count: int
    total_bytes: int
    created_at: str
    updated_at: str


class GithubImportInput(BaseModel):
    github_url: str


# ---------- Files & Symbols ----------

class RepoFile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    repo_id: str
    path: str                     # relative path
    language: Optional[str] = None
    size_bytes: int = 0
    line_count: int = 0
    is_binary: bool = False


class CodeSymbol(BaseModel):
    """A function, class, method, interface extracted from a file."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    repo_id: str
    file_path: str
    language: Optional[str] = None
    kind: Literal["function", "class", "method", "interface", "route", "variable"]
    name: str
    signature: Optional[str] = None
    parent: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    snippet: str = ""             # short code excerpt for retrieval


# ---------- Chat ----------

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    repo_id: str
    user_id: str
    role: Literal["user", "assistant"]
    content: str
    citations: List[dict] = Field(default_factory=list)     # [{path, start_line, end_line}]
    created_at: str = Field(default_factory=now_iso)


class ChatInput(BaseModel):
    message: str


class SearchInput(BaseModel):
    query: str
    limit: int = 10
