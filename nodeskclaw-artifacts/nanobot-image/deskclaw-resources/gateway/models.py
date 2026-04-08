from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    media: list[str] = Field(default_factory=list)


class ToolCallInfo(BaseModel):
    name: str
    input: dict
    output: str | None = None


class ChatResponse(BaseModel):
    run_id: str
    content: str
    session_id: str
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class SessionInfo(BaseModel):
    session_id: str
    message_count: int = 0
    created_at: str | None = None
    last_active: str | None = None
    channel: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]


class AbortResponse(BaseModel):
    success: bool
    session_id: str


# ── Cron Models ──

class CronScheduleInfo(BaseModel):
    kind: Literal["at", "every", "cron"]
    atMs: int | None = None
    everyMs: int | None = None
    expr: str | None = None
    tz: str | None = None


class CronPayloadInfo(BaseModel):
    kind: Literal["system_event", "agent_turn"] = "agent_turn"
    message: str = ""
    deliver: bool = False
    channel: str | None = None
    to: str | None = None


class CronJobStateInfo(BaseModel):
    nextRunAtMs: int | None = None
    lastRunAtMs: int | None = None
    lastStatus: Literal["ok", "error", "skipped"] | None = None
    lastError: str | None = None


class CronJobInfo(BaseModel):
    id: str
    name: str
    enabled: bool
    schedule: CronScheduleInfo
    payload: CronPayloadInfo
    state: CronJobStateInfo
    createdAtMs: int = 0
    updatedAtMs: int = 0
    deleteAfterRun: bool = False


class CronJobListResponse(BaseModel):
    jobs: list[CronJobInfo]


class CronToggleRequest(BaseModel):
    enabled: bool


class CronToggleResponse(BaseModel):
    success: bool
    job: CronJobInfo | None = None


class CronRunResponse(BaseModel):
    success: bool


class CronDeleteResponse(BaseModel):
    success: bool


class CronRunInfo(BaseModel):
    ts: int | None = None
    runAtMs: int | None = None
    status: str | None = None
    durationMs: int | None = None
    model: str | None = None
    error: str | None = None
    summary: str | None = None
    sessionKey: str | None = None


class CronRunListResponse(BaseModel):
    ok: bool = True
    runs: list[CronRunInfo] = []
    total: int = 0
    hasMore: bool = False


class CronStatusResponse(BaseModel):
    enabled: bool
    jobs: int
    nextWakeAtMs: int | None = None
