"""Actor declarations are untrusted personalization, never academic authority."""
from datetime import datetime
import unicodedata
from typing import Literal

from pydantic import Field, field_validator, model_validator
from campus247.application.assistance.contracts import StrictDTO, ResourceRef
from campus247.application.assistance.unified_contracts import UUID


class MemoryValue(StrictDTO):
    schema_version: Literal['assistant-memory.v1'] = 'assistant-memory.v1'
    kind: Literal['preference', 'goal', 'confirmed_fact']
    topic: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=1000)
    purpose: Literal['personal_assistance'] = 'personal_assistance'
    scope: Literal['actor', 'resource'] = 'actor'
    resource: ResourceRef | None = None
    grant_id: UUID | None = None
    valid_until: str
    origin: Literal['explicit_actor_declaration'] = 'explicit_actor_declaration'
    action_authority: Literal['none'] = 'none'

    @field_validator('topic', 'text')
    @classmethod
    def plain(cls, value):
        value = unicodedata.normalize('NFC', value).strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError('bounded plain declaration required')
        return value

    @model_validator(mode='after')
    def bindings(self):
        end = datetime.fromisoformat(self.valid_until)
        if end.utcoffset() is None:
            raise ValueError('timezone required')
        if (self.scope == 'resource') != (self.resource is not None) or (self.resource is None) != (self.grant_id is None):
            raise ValueError('exact resource and grant required together')
        return self


class MemoryChange(StrictDTO):
    operation: Literal['save', 'forget', 'control']
    client_id: UUID
    expected_version: int = Field(ge=0)
    conversation_id: UUID | None = None
    value: MemoryValue | None = None
    key: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    enabled: bool | None = None

    @model_validator(mode='after')
    def operation_shape(self):
        if self.operation == 'save':
            if self.value is None or self.enabled is not None or self.key is not None:
                raise ValueError('save requires declaration only')
        elif self.operation == 'forget':
            if self.key is None or self.expected_version < 1 or self.value is not None or self.enabled is not None:
                raise ValueError('forget requires exact existing key/version')
        elif self.enabled is None or self.key is not None or self.value is not None:
            raise ValueError('control requires explicit enabled')
        return self


class MemoryQuery(StrictDTO):
    conversation_id: UUID | None = None
    terms: list[str] = Field(min_length=1, max_length=8)
    resource: ResourceRef | None = None
    limit: int = Field(default=5, ge=1, le=5)

    @field_validator('terms')
    @classmethod
    def bounded_terms(cls, values):
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError('bounded search terms required')
        return [unicodedata.normalize('NFC', value).strip().casefold() for value in values]
