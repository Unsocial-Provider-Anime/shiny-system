from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.course import Identifier, StrictModel


class GenerateInteractionRequest(StrictModel):
    kind: Literal["action"]
    action: Literal["quiz-me"]
    lesson_id: Identifier | None = None


class SubmitQuizAnswerRequest(StrictModel):
    selected_option: Annotated[int, Field(ge=0, le=3)]


class GeneratedQuiz(StrictModel):
    question: Annotated[str, Field(min_length=1, max_length=2000)]
    options: Annotated[list[str], Field(min_length=2, max_length=4)]
    correct_option: Annotated[int, Field(ge=0, le=3)]
    explanation: Annotated[str, Field(min_length=1, max_length=4000)]

    @model_validator(mode="after")
    def correct_option_is_available(self) -> "GeneratedQuiz":
        if self.correct_option >= len(self.options):
            raise ValueError("correct_option must reference an available option")
        return self


class QuizInteractionResponse(StrictModel):
    id: UUID
    session_id: UUID
    lesson_id: Identifier
    kind: Literal["action"]
    action: Literal["quiz-me"]
    question: Annotated[str, Field(min_length=1, max_length=2000)]
    options: Annotated[list[str], Field(min_length=2, max_length=4)]
    selected_option: Annotated[int, Field(ge=0, le=3)] | None
    is_correct: bool | None
    explanation: Annotated[str, Field(min_length=1, max_length=4000)] | None
    created_at: str
