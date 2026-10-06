"""Request bodies. Field limits mirror what the services enforce."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Clock = Annotated[str, StringConstraints(min_length=5, max_length=5)]  # "HH:MM", validated by the domain
Id = Annotated[str, StringConstraints(max_length=64)]


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class AccountBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    enabled: bool = True
    cookie: str = Field("", max_length=16384)
    random_checkin: bool = True
    schedule_mode: Literal["fixed", "range"] = "fixed"
    schedule_time: Clock = "08:20"
    schedule_start: Clock = "08:20"
    schedule_end: Clock = "09:20"
    proxy_id: Id | None = None
    user_agent: str = Field("", max_length=512)
    keyword_monitor_enabled: bool = False
    keywords: list[str] = Field(default_factory=list, max_length=20)
    keyword_bot_id: Id | None = None
    keyword_chat_id: Id | None = None
    message_monitor_enabled: bool = False
    message_bot_id: Id | None = None
    message_chat_id: Id | None = None
    offline_notify_enabled: bool = False
    offline_bot_id: Id | None = None
    offline_chat_id: Id | None = None


class AccountUpdateBody(BaseModel):
    """Partial update: only the fields present in the request are changed."""

    name: str | None = Field(None, min_length=1, max_length=64)
    enabled: bool | None = None
    cookie: str | None = Field(None, max_length=16384)
    random_checkin: bool | None = None
    schedule_mode: Literal["fixed", "range"] | None = None
    schedule_time: Clock | None = None
    schedule_start: Clock | None = None
    schedule_end: Clock | None = None
    proxy_id: Id | None = None
    user_agent: str | None = Field(None, max_length=512)
    keyword_monitor_enabled: bool | None = None
    keywords: list[str] | None = Field(None, max_length=20)
    keyword_bot_id: Id | None = None
    keyword_chat_id: Id | None = None
    message_monitor_enabled: bool | None = None
    message_bot_id: Id | None = None
    message_chat_id: Id | None = None
    offline_notify_enabled: bool | None = None
    offline_bot_id: Id | None = None
    offline_chat_id: Id | None = None


class ProxyBody(BaseModel):
    name: str | None = Field(None, max_length=64)
    remark: str = Field("", max_length=240)
    proxy_url: str = Field(..., min_length=1, max_length=2048)


class ProxyUpdateBody(BaseModel):
    name: str | None = Field(None, max_length=64)
    remark: str | None = Field(None, max_length=240)
    proxy_url: str | None = Field(None, min_length=1, max_length=2048)


class BotBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    token: str = Field("", max_length=512)
    chat_id: str = Field(..., min_length=1, max_length=64)
    bot_id: Id | None = None
