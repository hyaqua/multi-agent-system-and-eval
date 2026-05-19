from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    base_url: str = Field(
        default="https://api.deepseek.com",
        description="API base URL. Examples: ",
    )
    api_key: str = Field(
        default="",
        description="API key. Use 'no-key-needed' for local models.",
    )
    model: str = Field(
        default="deepseek-v4-pro",
        description="Model name. Depends on your provider.",
    )
    reasoning_effort: str = Field(
        default="high",
        description="How much effort will be used for reasoning"
    )
    temperature: float = 0.2
    max_tokens: int = 65536


class DockerConfig(BaseModel):
    image: str = Field(
        default="multi-agent-sandbox",
        description="Docker image to use for code execution.",
    )
    timeout_seconds: int = Field(
        default=60,
        description="Max time for a single command execution.",
    )
    memory_limit: str = "1g"
    cpu_count: int = 1
    network_disabled: bool = True


class AgentConfig(BaseModel):
    max_iterations: int = Field(
        default=10,
        description="Max cycles before forced stop.",
    )
    max_total_tokens: int = Field(
        default=1_000_000,
        description="Token budget across all agents for one task.",
    )


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    docker: DockerConfig = DockerConfig()
    agent: AgentConfig = AgentConfig()
