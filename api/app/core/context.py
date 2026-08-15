from contextvars import ContextVar
from uuid import UUID

current_tenant_id: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)
