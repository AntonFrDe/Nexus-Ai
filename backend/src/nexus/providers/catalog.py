from pydantic import BaseModel, ConfigDict


class ProviderType(BaseModel):
    """What NEXUS knows about a kind of provider. Instances live in the database."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    default_endpoint: str | None
    endpoint_required: bool = False
    auth: str = "api_key"  # api_key, optional or none
    litellm_prefix: str
    discovery: str = "openai"  # openai, ollama, anthropic or manual
    local: bool = False
    # Calls cost money, so testing one needs explicit confirmation.
    paid: bool = True
    top_k: bool = False


PROVIDER_TYPES: list[ProviderType] = [
    ProviderType(
        id="ollama",
        title="Ollama",
        description="Local models served by Ollama.",
        default_endpoint="http://127.0.0.1:11434",
        auth="none",
        litellm_prefix="ollama_chat",
        discovery="ollama",
        local=True,
        paid=False,
        top_k=True,
    ),
    ProviderType(
        id="lm_studio",
        title="LM Studio",
        description="Local models served by LM Studio.",
        default_endpoint="http://127.0.0.1:1234/v1",
        auth="none",
        litellm_prefix="openai",
        local=True,
        paid=False,
    ),
    ProviderType(
        id="anthropic",
        title="Anthropic API",
        description="Paid API key. A Claude subscription does not work here.",
        default_endpoint="https://api.anthropic.com",
        litellm_prefix="anthropic",
        discovery="anthropic",
        top_k=True,
    ),
    ProviderType(
        id="openai",
        title="OpenAI API",
        description="OpenAI API key.",
        default_endpoint="https://api.openai.com/v1",
        litellm_prefix="openai",
    ),
    ProviderType(
        id="gemini",
        title="Google Gemini API",
        description="Gemini API key, billed apart from Google subscriptions.",
        default_endpoint=None,
        litellm_prefix="gemini",
        discovery="manual",
        top_k=True,
    ),
    ProviderType(
        id="mistral",
        title="Mistral API",
        description="Mistral API key.",
        default_endpoint="https://api.mistral.ai/v1",
        litellm_prefix="mistral",
    ),
    ProviderType(
        id="openrouter",
        title="OpenRouter",
        description="One key for many hosted models.",
        default_endpoint="https://openrouter.ai/api/v1",
        litellm_prefix="openrouter",
    ),
    ProviderType(
        id="litellm_gateway",
        title="LiteLLM Gateway",
        description="A LiteLLM proxy you run.",
        default_endpoint=None,
        endpoint_required=True,
        auth="optional",
        litellm_prefix="openai",
    ),
    ProviderType(
        id="openai_compatible",
        title="OpenAI-compatible endpoint",
        description="Any server with an OpenAI-style API.",
        default_endpoint=None,
        endpoint_required=True,
        auth="optional",
        litellm_prefix="openai",
    ),
]


def provider_type(type_id: str) -> ProviderType | None:
    return next((item for item in PROVIDER_TYPES if item.id == type_id), None)
