from __future__ import annotations


from enum import Enum




from pydantic import BaseModel, Field


class Source(str, Enum):
    FOUNDRY = "foundry"
    FABRIC = "fabric"
    WORK = "work"
    WEB = "web"


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class Evidence(BaseModel):
    refId: str
    source: Source
    title: str
    snippet: str
    url: str | None
    sourceType: str
