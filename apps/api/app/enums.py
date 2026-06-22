from enum import Enum


class WorkspaceStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class MemberRole(str, Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"


class MemberStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class SubscriptionStatus(str, Enum):
    active = "active"
    canceled = "canceled"
    past_due = "past_due"


class AgentStatus(str, Enum):
    draft    = "draft"
    active   = "active"
    inactive = "inactive"
    archived = "archived"
