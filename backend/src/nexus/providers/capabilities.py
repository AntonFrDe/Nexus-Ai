from typing import Any

from nexus.nodes.spec import FieldKind, FieldSpec

# Capability -> the OpenAI-style parameter that reveals it in LiteLLM's tables.
_SIGNALS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "max_tokens": "max_tokens",
    "reasoning_effort": "reasoning_effort",
    "streaming": "stream",
    "tool_calling": "tools",
    "structured_output": "response_format",
}
CAPABILITIES = [*_SIGNALS, "top_k"]


def capabilities_from_parameters(parameters: list[str], top_k: bool) -> dict[str, bool]:
    supported = set(parameters)
    detected = {name: signal in supported for name, signal in _SIGNALS.items()}
    return {**detected, "top_k": top_k}


def effective(capabilities: dict[str, bool], overrides: dict[str, bool]) -> dict[str, bool]:
    return {**capabilities, **overrides}


def _number(name: str, label: str, **options: Any) -> FieldSpec:
    return FieldSpec(name=name, label=label, kind=FieldKind.NUMBER, minimum=1, **options)


_PARAMETERS: dict[str, FieldSpec] = {
    "temperature": FieldSpec(
        name="temperature",
        label="Temperature",
        kind=FieldKind.SLIDER,
        minimum=0,
        maximum=2,
        step=0.05,
    ),
    "top_p": FieldSpec(
        name="top_p", label="Top P", kind=FieldKind.SLIDER, minimum=0, maximum=1, step=0.01
    ),
    "top_k": _number("top_k", "Top K"),
    "max_tokens": _number("max_tokens", "Max output tokens"),
    "reasoning_effort": FieldSpec(
        name="reasoning_effort",
        label="Reasoning effort",
        kind=FieldKind.SELECT,
        options=["low", "medium", "high"],
    ),
}


def parameter_fields(capabilities: dict[str, bool]) -> list[FieldSpec]:
    """Only what the model supports; an unsupported parameter has no field and fails validation."""
    return [field for name, field in _PARAMETERS.items() if capabilities.get(name)]
