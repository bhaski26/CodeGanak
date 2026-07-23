"""Workspace + membership + invite helpers.

Ownership of repositories has moved from users to workspaces. Any
user without a workspace is auto-migrated into a personal workspace
called "My workspace" on first access.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import HTTPException, status

from db import db
from models import (
    Workspace, Membership, Invite, Role, WorkspacePublic, WorkspaceMemberPublic,
)


ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}


async def ensure_personal_workspace(user_id: str) -> Workspace:
    """Idempotent: create the personal workspace and migrate legacy repos."""
    ws_doc = await db.workspaces.find_one({"owner_id": user_id, "is_personal": True}, {"_id": 0})
    if ws_doc:
        return Workspace(**ws_doc)

    ws = Workspace(name="My workspace", owner_id=user_id, is_personal=True)
    await db.workspaces.insert_one(ws.model_dump())
    await db.memberships.insert_one(
        Membership(workspace_id=ws.id, user_id=user_id, role="owner").model_dump()
    )
    # migrate any legacy repos owned by this user that have no workspace
    await db.repositories.update_many(
        {"user_id": user_id, "$or": [{"workspace_id": {"$exists": False}}, {"workspace_id": None}]},
        {"$set": {"workspace_id": ws.id}},
    )
    return ws


async def list_workspaces_for_user(user_id: str) -> List[WorkspacePublic]:
    await ensure_personal_workspace(user_id)
    memberships = await db.memberships.find({"user_id": user_id}, {"_id": 0}).to_list(200)
    out: List[WorkspacePublic] = []
    for m in memberships:
        ws = await db.workspaces.find_one({"id": m["workspace_id"]}, {"_id": 0})
        if not ws:
            continue
        repo_count = await db.repositories.count_documents({"workspace_id": ws["id"]})
        member_count = await db.memberships.count_documents({"workspace_id": ws["id"]})
        out.append(WorkspacePublic(
            id=ws["id"], name=ws["name"], owner_id=ws["owner_id"],
            is_personal=ws.get("is_personal", False), role=m["role"],
            created_at=ws["created_at"],
            repo_count=repo_count, member_count=member_count,
        ))
    out.sort(key=lambda w: (not w.is_personal, w.name.lower()))
    return out


async def get_membership(workspace_id: str, user_id: str) -> Optional[Membership]:
    doc = await db.memberships.find_one({"workspace_id": workspace_id, "user_id": user_id}, {"_id": 0})
    return Membership(**doc) if doc else None


async def require_membership(workspace_id: str, user_id: str, min_role: Role = "member") -> Membership:
    m = await get_membership(workspace_id, user_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace")
    if ROLE_RANK[m.role] < ROLE_RANK[min_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{m.role}' insufficient (needs '{min_role}')",
        )
    return m


async def create_workspace(user_id: str, name: str) -> WorkspacePublic:
    ws = Workspace(name=name, owner_id=user_id, is_personal=False)
    await db.workspaces.insert_one(ws.model_dump())
    await db.memberships.insert_one(
        Membership(workspace_id=ws.id, user_id=user_id, role="owner").model_dump()
    )
    return WorkspacePublic(
        id=ws.id, name=ws.name, owner_id=ws.owner_id,
        is_personal=False, role="owner", created_at=ws.created_at,
        repo_count=0, member_count=1,
    )


async def rename_workspace(workspace_id: str, user_id: str, new_name: str) -> None:
    await require_membership(workspace_id, user_id, min_role="admin")
    await db.workspaces.update_one({"id": workspace_id}, {"$set": {"name": new_name}})


async def delete_workspace(workspace_id: str, user_id: str) -> None:
    m = await require_membership(workspace_id, user_id, min_role="owner")
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.get("is_personal"):
        raise HTTPException(status_code=400, detail="Cannot delete personal workspace")
    # cascade: remove memberships, invites, and repos
    repo_ids = [r["id"] async for r in db.repositories.find({"workspace_id": workspace_id}, {"_id": 0, "id": 1})]
    if repo_ids:
        await db.files.delete_many({"repo_id": {"$in": repo_ids}})
        await db.symbols.delete_many({"repo_id": {"$in": repo_ids}})
        await db.imports.delete_many({"repo_id": {"$in": repo_ids}})
        await db.chat_messages.delete_many({"repo_id": {"$in": repo_ids}})
        await db.repositories.delete_many({"workspace_id": workspace_id})
    await db.memberships.delete_many({"workspace_id": workspace_id})
    await db.invites.delete_many({"workspace_id": workspace_id})
    await db.workspaces.delete_one({"id": workspace_id})
    _ = m


async def list_members(workspace_id: str, user_id: str) -> List[WorkspaceMemberPublic]:
    await require_membership(workspace_id, user_id, min_role="member")
    members = await db.memberships.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    out: List[WorkspaceMemberPublic] = []
    for m in members:
        u = await db.users.find_one({"id": m["user_id"]}, {"_id": 0})
        if not u:
            continue
        out.append(WorkspaceMemberPublic(
            user_id=u["id"], email=u["email"], name=u["name"],
            role=m["role"], joined_at=m["joined_at"],
        ))
    out.sort(key=lambda x: (ROLE_RANK.get(x.role, 0) * -1, x.name.lower()))
    return out


async def update_member_role(
    workspace_id: str, actor_id: str, target_user_id: str, new_role: Role,
) -> None:
    actor = await require_membership(workspace_id, actor_id, min_role="admin")
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws["owner_id"] == target_user_id and new_role != "owner":
        raise HTTPException(status_code=400, detail="Cannot demote workspace owner")
    if new_role == "owner" and actor.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can transfer ownership")
    await db.memberships.update_one(
        {"workspace_id": workspace_id, "user_id": target_user_id},
        {"$set": {"role": new_role}},
    )


async def remove_member(workspace_id: str, actor_id: str, target_user_id: str) -> None:
    await require_membership(workspace_id, actor_id, min_role="admin")
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws["owner_id"] == target_user_id:
        raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
    await db.memberships.delete_one({"workspace_id": workspace_id, "user_id": target_user_id})


async def create_invite(workspace_id: str, actor_id: str, role: Role) -> Invite:
    await require_membership(workspace_id, actor_id, min_role="admin")
    inv = Invite(workspace_id=workspace_id, role=role, created_by=actor_id)
    await db.invites.insert_one(inv.model_dump())
    return inv


async def list_invites(workspace_id: str, actor_id: str) -> List[Invite]:
    await require_membership(workspace_id, actor_id, min_role="admin")
    docs = await db.invites.find(
        {"workspace_id": workspace_id, "revoked": False}, {"_id": 0},
    ).sort("created_at", -1).to_list(50)
    return [Invite(**d) for d in docs]


async def revoke_invite(workspace_id: str, actor_id: str, invite_id: str) -> None:
    await require_membership(workspace_id, actor_id, min_role="admin")
    await db.invites.update_one(
        {"id": invite_id, "workspace_id": workspace_id},
        {"$set": {"revoked": True}},
    )


async def accept_invite(token: str, user_id: str) -> Tuple[Workspace, str]:
    inv = await db.invites.find_one({"token": token, "revoked": False}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found or revoked")
    ws = await db.workspaces.find_one({"id": inv["workspace_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace no longer exists")

    existing = await db.memberships.find_one(
        {"workspace_id": ws["id"], "user_id": user_id}, {"_id": 0},
    )
    if existing:
        return Workspace(**ws), existing["role"]

    m = Membership(workspace_id=ws["id"], user_id=user_id, role=inv["role"])
    await db.memberships.insert_one(m.model_dump())
    return Workspace(**ws), m.role


async def preview_invite(token: str) -> dict:
    inv = await db.invites.find_one({"token": token, "revoked": False}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found or revoked")
    ws = await db.workspaces.find_one({"id": inv["workspace_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace no longer exists")
    owner = await db.users.find_one({"id": ws["owner_id"]}, {"_id": 0, "name": 1, "email": 1})
    return {
        "workspace_id": ws["id"],
        "workspace_name": ws["name"],
        "role": inv["role"],
        "owner_name": (owner or {}).get("name", "someone"),
    }
