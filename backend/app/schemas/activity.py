from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.course import Identifier, NonEmptyText, StrictModel


class TextAndImagesContent(StrictModel):
    type: Literal["text-and-images"]
    content: Annotated[str, Field(min_length=1, max_length=12000)]
    image_descriptions: Annotated[list[NonEmptyText], Field(max_length=4)] = Field(
        default_factory=list
    )


class GeneratedLessonActivity(StrictModel):
    presentation_format: Literal["text-and-images"]
    content: TextAndImagesContent


class LessonActivityResponse(GeneratedLessonActivity):
    id: UUID
    session_id: UUID
    lesson_id: Identifier
    created_at: str
