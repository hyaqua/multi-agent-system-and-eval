from __future__ import annotations

import time
from enum import Enum

from pydantic import BaseModel, Field


class Phase(str, Enum):
    PLANNING = "planning"
    CODING = "coding"
    TESTING = "testing"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"


class TestResult(BaseModel):
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class ReviewVerdict(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"


class ReviewResult(BaseModel):
    verdict: ReviewVerdict
    working_features: list[str] = Field(default_factory=list)
    missing_features: list[str] = Field(default_factory=list)
    bugs: list[str] = Field(default_factory=list)
    suggestions: str = ""


class AgentState(BaseModel):

    task_name: str = ""
    task_spec: str = ""
    required_features: list[str] = Field(default_factory=list)

    phase: Phase = Phase.PLANNING
    iteration: int = 0

    # Agent outputs
    plan: str = ""
    code_files: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of filepath -> file contents produced by the coder.",
    )
    test_result: TestResult | None = None
    review: ReviewResult | None = None

    iteration_history: list[dict] = Field(
        default_factory=list,
        description="Snapshot of each iteration for thesis analysis.",
    )

    total_tokens_used: int = 0

    # Timing
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None

    # Container ID
    container_id: str | None = None
    work_dir: str = ""
