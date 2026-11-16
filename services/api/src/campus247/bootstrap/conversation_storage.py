"""Explicit repository selection. A configured durable store never falls back."""
from campus247.application.conversation.messages import InMemoryConversationRepository
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository


def conversation_storage(settings, provided=None, *, tenant=None):
    mode = settings.CONVERSATION_STORAGE_MODE
    if provided is not None:
        if mode == "sqlite":
            raise ValueError("choose configured SQLite or explicit injection, not both")
        if not all(callable(getattr(provided,key,None)) for key in
                   ("save_conversation","get_conversation","save_message","list_messages","get_next_sequence_no")):
            raise ValueError("conversation repository port incomplete")
        repository = provided
        mode = "injected"
    elif mode == "injected":
        raise ValueError("configured conversation repository missing")
    elif mode == "sqlite":
        if settings.ENVIRONMENT not in {"development","testing"} or not settings.DEMO_MODE:
            raise ValueError("local SQLite requires explicit synthetic environment")
        if settings.CONVERSATION_SQLITE_PATH is None:
            raise ValueError("explicit conversation SQLite path required")
        repository = SQLiteConversationRepository(settings.CONVERSATION_SQLITE_PATH)
    else:
        repository = InMemoryConversationRepository()
    durability = "durable" if isinstance(repository,SQLiteConversationRepository) else "ephemeral" if isinstance(repository,InMemoryConversationRepository) else "unverified"
    if tenant is not None and isinstance(repository,SQLiteConversationRepository):
        repository.bind_tenant(tenant)
    if settings.ENVIRONMENT in {"staging","production"} and durability != "durable":
        raise ValueError("durable conversation repository required")
    return repository, {"mode":mode,"durability":durability,"fallback":False}
