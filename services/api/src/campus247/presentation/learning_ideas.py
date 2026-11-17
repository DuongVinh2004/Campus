"""Request shapes and routes for version-bound idea cards."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Prose = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Status = Literal["ACTIVE", "ARCHIVED"]


class LearningIdeaRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(strict=True, ge=0, le=1)
    y: float = Field(strict=True, ge=0, le=1)
    width: float = Field(strict=True, gt=0, le=1)
    height: float = Field(strict=True, gt=0, le=1)


class LearningIdeaSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: UUID
    page_no: int = Field(strict=True, ge=1, le=500)
    kind: Literal["PAGE", "TEXT", "REGION"]
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None
    rects: list[LearningIdeaRegion] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def exact_source_shape(self):
        if (self.quote is not None) != (self.kind == "TEXT") or bool(self.rects) != (self.kind == "REGION"):
            raise ValueError("Idea source must have exactly the anchor for its selected kind")
        return self


def idea_input_models(model):
    card_fields = {
        "topic_id": (UUID | None, None),
        "problem": (Prose, ...),
        "idea": (Prose, ...),
        "verification": (Prose, ...),
        "source_description": (Description, ""),
    }
    return {
        "idea-topic-create": model("LearningIdeaTopicInput", title=(Title, ...)),
        "idea-topic-update": model("LearningIdeaTopicUpdate", title=(Title, ...), status=(Status, ...),
                                   revision=(int, Field(strict=True, ge=1))),
        "idea-card-create": model("LearningIdeaCardInput", source=(LearningIdeaSource, ...), **card_fields),
        "idea-card-update": model("LearningIdeaCardUpdate", status=(Status, ...), revision=(int, Field(strict=True, ge=1)),
                                  **card_fields),
        "idea-share-create": model("LearningIdeaShareInput", revision=(int, Field(strict=True, ge=1)),
                                   recipient_ids=(list[UUID], Field(min_length=1, max_length=20))),
        "idea-share-withdraw": model("LearningIdeaShareWithdraw", revision=(int, Field(strict=True, ge=1))),
    }


def register_idea_routes(router, read_endpoint, write_endpoint):
    for path, kind, target in (
        ("/me/idea-topics", "idea_topics", None),
        ("/me/idea-cards", "idea_cards", None),
        ("/me/idea-cards/{card_id}", "idea_card", "card_id"),
        ("/me/idea-cards/{card_id}/recipients", "idea_recipients", "card_id"),
        ("/me/idea-shares", "idea_shares", None),
        ("/shared-idea-cards", "shared_ideas", None),
        ("/shared-idea-cards/{share_id}", "shared_idea", "share_id"),
    ):
        router.add_api_route(path, read_endpoint(kind, target), methods=["GET"], name=f"learning_{kind}")
    for path, method, action, target in (
        ("/me/idea-topics", "POST", "idea-topic-create", None),
        ("/me/idea-topics/{topic_id}", "PATCH", "idea-topic-update", "topic_id"),
        ("/me/idea-cards", "POST", "idea-card-create", None),
        ("/me/idea-cards/{card_id}", "PATCH", "idea-card-update", "card_id"),
        ("/me/idea-cards/{card_id}/shares", "POST", "idea-share-create", "card_id"),
        ("/me/idea-shares/{share_id}", "PATCH", "idea-share-withdraw", "share_id"),
    ):
        router.add_api_route(path, write_endpoint(action, target), methods=[method], name=f"learning_{action}")
