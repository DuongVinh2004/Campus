"""Request shapes and routes for practice questions."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from uuid import UUID

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Prompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Explanation = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class LearningPracticeOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,16}$")]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class LearningPracticeCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_no: int = Field(strict=True, ge=1, le=500)
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=500)]


def practice_input_models(model):
    return {
        "practice-set-create": model("LearningPracticeSetInput", version_id=(UUID, ...), title=(Title, ...)),
        "practice-item-save": model(
            "LearningPracticeItemInput", revision=(int, Field(strict=True, ge=1)), item_id=(UUID | None, None),
            kind=(Literal["single_choice", "multi_choice", "short_answer"], ...), prompt=(Prompt, ...),
            options=(list[LearningPracticeOption], Field(default_factory=list, max_length=6)),
            answer=(list[str], Field(default_factory=list, max_length=6)),
            accepted=(list[Annotated[str, StringConstraints(max_length=200)]], Field(default_factory=list, max_length=5)),
            explanation=(Explanation, ""), citations=(list[LearningPracticeCitation], Field(min_length=1, max_length=3)),
        ),
        "practice-set-publish": model("LearningPracticePublish", revision=(int, Field(strict=True, ge=1))),
        "practice-attempt-save": model(
            "LearningPracticeAttempt", choices=(list[str] | None, Field(default=None, max_length=6)),
            text=(Annotated[str, StringConstraints(max_length=500)] | None, None),
        ),
    }


def register_practice_routes(router, read_endpoint, write_endpoint):
    for path, kind, target in (
        ("/sessions/{session_id}/practice-sets", "practice_sets", "session_id"),
        ("/practice-sets/{set_id}", "practice_set", "set_id"),
        ("/practice-sets/{set_id}/session", "practice_session", "set_id"),
        ("/practice-sets/{set_id}/stats", "practice_stats", "set_id"),
    ):
        router.add_api_route(path, read_endpoint(kind, target), methods=["GET"], name=f"learning_{kind}")
    for path, method, action, target in (
        ("/sessions/{session_id}/practice-sets", "POST", "practice-set-create", "session_id"),
        ("/practice-sets/{set_id}/items", "PUT", "practice-item-save", "set_id"),
        ("/practice-sets/{set_id}/publication", "POST", "practice-set-publish", "set_id"),
        ("/practice-items/{item_id}/attempts", "POST", "practice-attempt-save", "item_id"),
    ):
        router.add_api_route(path, write_endpoint(action, target), methods=[method], name=f"learning_{action}")
