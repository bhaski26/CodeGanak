"""Pydantic + Mongo models for CodeGanak."""
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


# ---------- Workspaces / Membership / Invites ----------

Role = Literal["owner", "admin", "member"]


class Workspace(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    name: str
    owner_id: str
    is_personal: bool = False
    created_at: str = Field(default_factory=now_iso)


class Membership(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    workspace_id: str
    user_id: str
    role: Role = "member"
    joined_at: str = Field(default_factory=now_iso)


class Invite(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    workspace_id: str
    token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    role: Role = "member"
    created_by: str
    created_at: str = Field(default_factory=now_iso)
    revoked: bool = False


class WorkspaceCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WorkspaceRenameInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class InviteCreateInput(BaseModel):
    role: Role = "member"


class RoleUpdateInput(BaseModel):
    role: Role


class WorkspaceMemberPublic(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    role: Role
    joined_at: str


class WorkspacePublic(BaseModel):
    id: str
    name: str
    owner_id: str
    is_personal: bool
    role: Role
    created_at: str
    repo_count: int = 0
    member_count: int = 0


# ---------- Repository ----------

RepoStatus = Literal["queued", "cloning", "parsing", "indexing", "ready", "failed"]


class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    workspace_id: str
    user_id: str                                          # importer / creator
    name: str
    source: Literal["zip", "github"]
    github_url: Optional[str] = None
    status: RepoStatus = "queued"
    error: Optional[str] = None
    languages: dict = Field(default_factory=dict)
    primary_language: Optional[str] = None
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    file_count: int = 0
    function_count: int = 0
    class_count: int = 0
    api_count: int = 0
    total_bytes: int = 0
    root_path: Optional[str] = None
    embedding_ready: bool = False
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class RepositoryPublic(BaseModel):
    id: str
    workspace_id: str
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
    embedding_ready: bool = False
    created_at: str
    updated_at: str


class GithubImportInput(BaseModel):
    github_url: str
    workspace_id: Optional[str] = None


# ---------- Files & Symbols ----------

class RepoFile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    repo_id: str
    path: str
    language: Optional[str] = None
    size_bytes: int = 0
    line_count: int = 0
    is_binary: bool = False


class CodeSymbol(BaseModel):
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
    snippet: str = ""


class ImportEdge(BaseModel):
    """A single import statement resolved (or unresolved) to a target file/module."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    repo_id: str
    source_path: str
    raw: str                              # raw import text (e.g. "from x import y")
    target_path: Optional[str] = None     # resolved path within repo, if any
    target_module: Optional[str] = None   # raw module string
    is_external: bool = False


# ---------- Chat ----------

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    repo_id: str
    user_id: str
    role: Literal["user", "assistant"]
    content: str
    citations: List[dict] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class ChatInput(BaseModel):
    message: str


class SearchInput(BaseModel):
    query: str
    limit: int = 10
