from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.course import (
    Identifier,
    NonEmptyText,
    PresentationFormat,
    StrictModel,
)

LessonActivityAction = Literal[
    "teach",
    "explain-another-way",
    "give-example",
    "answer-question",
    "change-format",
]


class GenerateLessonActivityRequest(StrictModel):
    regenerate: bool = False
    presentation_format: PresentationFormat | None = None
    action: LessonActivityAction = "teach"
    question: Annotated[str, Field(min_length=1, max_length=2000)] | None = None

    @model_validator(mode="after")
    def validate_action_request(self) -> "GenerateLessonActivityRequest":
        if self.action == "answer-question" and self.question is None:
            raise ValueError("question is required for answer-question")
        if self.action != "answer-question" and self.question is not None:
            raise ValueError("question is only allowed for answer-question")
        if self.action == "change-format" and self.presentation_format is None:
            raise ValueError("presentation_format is required for change-format")
        return self


class TextAndImagesContent(StrictModel):
    type: Literal["text-and-images"]
    content: Annotated[str, Field(min_length=1, max_length=12000)]
    image_descriptions: Annotated[list[NonEmptyText], Field(max_length=4)] = Field(
        default_factory=list
    )


class SimulationChoice(StrictModel):
    label: Annotated[str, Field(min_length=1, max_length=200)]
    consequence: NonEmptyText


class SimulationContent(StrictModel):
    type: Literal["interactive-simulations"]
    scenario: NonEmptyText
    choices: Annotated[list[SimulationChoice], Field(min_length=2, max_length=5)]
    learning_point: NonEmptyText


class RolePlayChoice(StrictModel):
    response: Annotated[str, Field(min_length=1, max_length=1000)]
    feedback: NonEmptyText


class RolePlayContent(StrictModel):
    type: Literal["interactive-role-play-activities"]
    scenario: NonEmptyText
    learner_role: Annotated[str, Field(min_length=1, max_length=200)]
    partner_role: Annotated[str, Field(min_length=1, max_length=200)]
    opening_prompt: NonEmptyText
    response_choices: Annotated[
        list[RolePlayChoice], Field(min_length=2, max_length=4)
    ]


class GameChoice(StrictModel):
    label: Annotated[str, Field(min_length=1, max_length=200)]
    is_correct: bool
    feedback: NonEmptyText


class GameContent(StrictModel):
    type: Literal["games"]
    objective: NonEmptyText
    instructions: NonEmptyText
    challenge: NonEmptyText
    choices: Annotated[list[GameChoice], Field(min_length=2, max_length=5)]

    @model_validator(mode="after")
    def has_correct_and_incorrect_choices(self) -> "GameContent":
        if not any(choice.is_correct for choice in self.choices):
            raise ValueError("a game must have at least one correct choice")
        if all(choice.is_correct for choice in self.choices):
            raise ValueError("a game must have at least one incorrect choice")
        return self


class AnimationScene(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    visual_description: NonEmptyText
    narration: NonEmptyText


class AnimationContent(StrictModel):
    type: Literal["animations"]
    scenes: Annotated[list[AnimationScene], Field(min_length=2, max_length=8)]


class Slide(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    content: NonEmptyText


class SlidesContent(StrictModel):
    type: Literal["slides-based"]
    slides: Annotated[list[Slide], Field(min_length=2, max_length=12)]


class CodingContent(StrictModel):
    type: Literal["online-coding"]
    instructions: NonEmptyText
    starter_code: Annotated[str, Field(max_length=6000)]
    expected_code: Annotated[str, Field(min_length=1, max_length=6000)]
    explanation: NonEmptyText


ActivityContent = Annotated[
    TextAndImagesContent
    | SimulationContent
    | RolePlayContent
    | GameContent
    | AnimationContent
    | SlidesContent
    | CodingContent,
    Field(discriminator="type"),
]


class GeneratedLessonActivity(StrictModel):
    presentation_format: PresentationFormat
    content: ActivityContent

    @model_validator(mode="after")
    def format_matches_content(self) -> "GeneratedLessonActivity":
        if self.presentation_format != self.content.type:
            raise ValueError("presentation_format must match content.type")
        return self


class LessonActivityResponse(GeneratedLessonActivity):
    id: UUID
    session_id: UUID
    lesson_id: Identifier
    created_at: str
