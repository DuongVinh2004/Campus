"""Request shapes and routes for concepts, mastery and the tutor (F7).

Routes sit under /v1/learning/mastery/* (feature `learning.mastery_map`) and /v1/learning/tutor/* (feature `learning.tutor`), so the
feature gate turns each part off on its own.
"""
import csv
import io
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)]


class LearningConceptLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["PRACTICE_ITEM", "PAGE"]
    target: Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[0-9a-fA-F-]{36}(?::[0-9]{1,3})?$")]
    weight: float = Field(default=1.0, gt=0, le=1)


class LearningHintInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    more: bool = False
    solution: bool = False
    reply: Annotated[str, StringConstraints(max_length=500)] | None = None


def tutor_input_models(model):
    return {
        "concept-create": model("LearningConceptInput", label=(Label, ...), description=(Description, ""),
                                links=(list[LearningConceptLink], Field(default_factory=list, max_length=200))),
        "concept-update": model("LearningConceptUpdate", revision=(int, Field(strict=True, ge=1)), label=(Label | None, None),
                                description=(Description | None, None), links=(list[LearningConceptLink] | None, Field(default=None, max_length=200)),
                                status=(Literal["APPROVED", "RETIRED"] | None, None)),
        "tutor-settings-save": model("LearningTutorSettings", revision=(int, Field(strict=True, ge=0)), tutor_enabled=(bool, ...),
                                     reveal_after_attempts=(int, Field(strict=True, ge=1, le=5)), model_hints_enabled=(bool, ...)),
    }


def map_csv(result: dict[str, Any]) -> str:
    """Aggregated numbers only (the same k >= 5 rules as the map); no student appears."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["khai_niem", "so_sinh_vien", "nam_vung", "dang_tien_bo", "can_on", "chua_du_du_lieu", "ti_le_can_on"])
    for row in result.get("concepts", []):
        bands = row.get("bands") or {}
        writer.writerow([row["label"], row["students"], bands.get("MASTERED", ""), bands.get("PROGRESSING", ""), bands.get("NEEDS_REVIEW", ""),
                         bands.get("NOT_ENOUGH_DATA", ""), "" if row.get("needs_review_rate") is None else row["needs_review_rate"]])
    return out.getvalue()


def register_tutor_routes(router, read_endpoint, write_endpoint, actor, service):
    for path, kind in (
        ("/mastery/offerings/{offering_id}/concepts", "concepts"),
        ("/mastery/offerings/{offering_id}/me", "my_mastery"),
        ("/mastery/offerings/{offering_id}/map", "mastery_map"),
        ("/tutor/offerings/{offering_id}/settings", "tutor_settings"),
    ):
        router.add_api_route(path, read_endpoint(kind, "offering_id"), methods=["GET"], name=f"learning_{kind}")
    for path, method, action, target in (
        ("/mastery/offerings/{offering_id}/concepts", "POST", "concept-create", "offering_id"),
        ("/mastery/concepts/{concept_id}", "PATCH", "concept-update", "concept_id"),
        ("/tutor/offerings/{offering_id}/settings", "PUT", "tutor-settings-save", "offering_id"),
    ):
        router.add_api_route(path, write_endpoint(action, target), methods=[method], name=f"learning_{action}")

    @router.get("/mastery/offerings/{offering_id}/map.csv", name="learning_mastery_map_csv")
    async def map_export(request: Request, offering_id: UUID):
        current = actor(request)
        result = await service.query(current, "mastery_map", str(offering_id))
        return Response(map_csv(result), media_type="text/csv; charset=utf-8",
                        headers={"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="ban-do-nam-vung.csv"'})

    @router.post("/mastery/offerings/{offering_id}/concept-suggestions", name="learning_concept_suggestions")
    async def suggest(request: Request, offering_id: UUID):
        from campus247.features import runtime
        current = actor(request, write=True)
        result = await service.suggest_concepts(current, str(offering_id), still_valid=lambda: actor(request, write=True),
                                                model_allowed=runtime.value("learning.ai_explanations", False) is True)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @router.post("/tutor/practice-items/{item_id}/hints", name="learning_tutor_hint")
    async def hint(request: Request, item_id: UUID, body: LearningHintInput):
        from campus247.features import runtime
        current = actor(request, write=True)
        # A model may write hints only while the system-wide AI explanations feature is on (decision D8); otherwise templates only.
        result = await service.tutor_hint(current, str(item_id), body.model_dump(), still_valid=lambda: actor(request, write=True),
                                          model_allowed=runtime.value("learning.ai_explanations", False) is True)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
