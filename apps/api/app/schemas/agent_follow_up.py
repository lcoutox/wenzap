from pydantic import BaseModel, ConfigDict, Field, model_validator

_MAX_STEPS = 5
_MIN_DELAY_HOURS = 1
_MAX_DELAY_HOURS = 500


class AgentFollowUpStepOut(BaseModel):
    step_order: int
    delay_hours: int
    custom_instructions: str | None

    model_config = ConfigDict(from_attributes=True)


class AgentFollowUpStepInput(BaseModel):
    """step_order is NOT accepted here — it's assigned from list position on
    save (0-indexed), so the operator only ever thinks in terms of "the Nth
    step", never a number they have to keep in sync themselves.

    custom_instructions is optional and specific to this step — combined
    with (not replacing) AgentFollowUpSettingsUpdate.custom_instructions,
    which applies to every step."""

    delay_hours: int = Field(ge=_MIN_DELAY_HOURS, le=_MAX_DELAY_HOURS)
    custom_instructions: str | None = Field(default=None, max_length=1000)


class AgentFollowUpSettingsOut(BaseModel):
    is_enabled: bool
    custom_instructions: str | None
    steps: list[AgentFollowUpStepOut]

    model_config = ConfigDict(from_attributes=True)


class AgentFollowUpSettingsUpdate(BaseModel):
    is_enabled: bool
    custom_instructions: str | None = Field(default=None, max_length=1000)
    # Full replace on every save — same simplicity as the Pipeline stage
    # reorder endpoint. Order in the list IS the step_order.
    steps: list[AgentFollowUpStepInput] = Field(default_factory=list, max_length=_MAX_STEPS)

    @model_validator(mode="after")
    def validate_steps_strictly_increasing(self) -> "AgentFollowUpSettingsUpdate":
        if self.is_enabled and not self.steps:
            raise ValueError("Configure ao menos um degrau de follow-up para ativar.")
        hours = [s.delay_hours for s in self.steps]
        if hours != sorted(set(hours)):
            raise ValueError(
                "Os prazos dos degraus devem ser crescentes e sem repetição "
                "(ex: 6, 24, 72)."
            )
        return self
