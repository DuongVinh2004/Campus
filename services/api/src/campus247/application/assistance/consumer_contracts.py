"""Shared display content: no executable actions or trusted prose inference."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from campus247.application.assistance.contracts import StrictDTO

Text = Annotated[str, Field(max_length=4000)]


class StepsBlock(StrictDTO):
    type: Literal["steps"]
    items: list[Text] = Field(max_length=20)


class TableBlock(StrictDTO):
    type: Literal["table"]
    columns: list[Text] = Field(min_length=1, max_length=12)
    rows: list[list[Text]] = Field(max_length=100)

    @model_validator(mode="after")
    def shape(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("table column binding required")
        return self


class StatusBlock(StrictDTO):
    type: Literal["status"]
    state: Literal["pending", "completed", "interrupted", "error"]
    text: Text


class DisplayChange(StrictDTO):
    field: Text
    before: Text
    after: Text


class ProposalBlock(StrictDTO):
    type: Literal["proposal"]
    title: Text
    changes: list[DisplayChange] = Field(max_length=30)
    action_authority: Literal["none"] = "none"


class NavigationBlock(StrictDTO):
    type: Literal["navigation"]
    label: Text
    path: Literal["/services", "/my-requests", "/privacy", "/student/certificate", "/student/complaint", "/staff"]
    audience: Literal["student", "staff"]

    @model_validator(mode="after")
    def audience_path(self):
        allowed = {"student": {"/services", "/my-requests", "/privacy", "/student/certificate", "/student/complaint"},
                   "staff": {"/staff", "/privacy"}}
        if self.path not in allowed[self.audience]:
            raise ValueError("navigation audience mismatch")
        return self


Block = Annotated[StepsBlock | TableBlock | StatusBlock | ProposalBlock | NavigationBlock, Field(discriminator="type")]


class AssistantDisplayContent(StrictDTO):
    schema_version: Literal["assistant-content.v1"] = "assistant-content.v1"
    content: str = Field(max_length=20000)
    blocks: list[Block] = Field(default_factory=list, max_length=12)
