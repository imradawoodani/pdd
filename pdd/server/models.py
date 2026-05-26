"""
Pydantic v2 models for the PDD Server REST API.

This module defines the data structures for request and response bodies used
in file operations, command execution, job management, and WebSocket messaging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "FileMetadata",
    "FileTreeNode",
    "FileContent",
    "WriteFileRequest",
    "WriteResult",
    "CommandRequest",
    "JobHandle",
    "JobStatus",
    "JobResult",
    "WSMessage",
    "StdoutMessage",
    "StderrMessage",
    "ProgressMessage",
    "InputRequestMessage",
    "CompleteMessage",
    "FileChangeMessage",
    "ServerStatus",
    "ServerConfig",
    "RemoteSessionInfo",
    "SessionListItem",
    "TokenBreakdown",
    "CostEstimate",
    "TokenMetrics",
    "ContextAudit",
    "ContextAuditResponse",
    "ArchitectureModule",
    "ValidationError",
    "ValidationWarning",
    "ValidateArchitectureRequest",
    "ValidationResult",
    "SyncRequest",
    "SyncResult",
    "GenerateTagsRequest",
    "GenerateTagsResult",
    "RearrangeRequest",
    "RearrangeResult",
]


# ============================================================================
# File Models
# ============================================================================

class FileMetadata(BaseModel):
    """Metadata for a single file or directory."""
    path: str = Field(..., description="Relative path from project root")
    exists: bool = Field(..., description="Whether the file exists on disk")
    size: Optional[int] = Field(None, description="File size in bytes")
    mtime: Optional[datetime] = Field(None, description="Last modification time")
    is_directory: bool = Field(False, description="True if path is a directory")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal ('..') is not allowed")
        return v


class FileTreeNode(BaseModel):
    """Recursive tree structure for file system navigation."""
    name: str = Field(..., description="Base name of the file/directory")
    path: str = Field(..., description="Relative path from project root")
    type: Literal["file", "directory"] = Field(..., description="Node type")
    children: Optional[List[FileTreeNode]] = Field(None, description="Child nodes if directory")
    size: Optional[int] = Field(None, description="File size in bytes")
    mtime: Optional[datetime] = Field(None, description="Last modification time")


class FileContent(BaseModel):
    """Content of a file, potentially encoded."""
    path: str = Field(..., description="Relative path from project root")
    content: str = Field(..., description="File content (text or base64)")
    encoding: Literal["utf-8", "base64"] = Field("utf-8", description="Content encoding")
    size: int = Field(..., description="Size of content in bytes")
    is_binary: bool = Field(False, description="True if content is binary data")
    chunk_index: Optional[int] = Field(None, description="Index if chunked transfer")
    total_chunks: Optional[int] = Field(None, description="Total chunks if chunked transfer")
    checksum: Optional[str] = Field(None, description="SHA-256 checksum of content")


class WriteFileRequest(BaseModel):
    """Request to write content to a file."""
    path: str = Field(..., description="Relative path from project root")
    content: str = Field(..., description="Content to write")
    encoding: Literal["utf-8", "base64"] = Field("utf-8", description="Content encoding")
    create_parents: bool = Field(True, description="Create parent directories if missing")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal ('..') is not allowed")
        return v


class WriteResult(BaseModel):
    """Result of a file write operation."""
    success: bool = Field(..., description="Whether the write succeeded")
    path: str = Field(..., description="Path written to")
    mtime: Optional[datetime] = Field(None, description="New modification time")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# Command & Job Models
# ============================================================================

class CommandRequest(BaseModel):
    """Request to execute a PDD command."""
    command: str = Field(..., description="PDD command name (e.g., 'sync', 'generate')")
    args: Dict[str, Any] = Field(default_factory=dict, description="Positional arguments")
    options: Dict[str, Any] = Field(default_factory=dict, description="Command options/flags")


class JobStatus(str, Enum):
    """Enumeration of possible job statuses."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobHandle(BaseModel):
    """Initial response after submitting a command."""
    job_id: str = Field(..., description="Unique identifier for the job")
    status: JobStatus = Field(JobStatus.QUEUED, description="Current status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Submission timestamp")


class JobResult(BaseModel):
    """Final result of a completed job."""
    job_id: str = Field(..., description="Unique identifier for the job")
    status: JobStatus = Field(..., description="Final status")
    result: Optional[Any] = Field(None, description="Command return value")
    error: Optional[str] = Field(None, description="Error message if failed")
    cost: float = Field(0.0, description="Estimated cost of operation")
    duration_seconds: float = Field(0.0, description="Execution duration")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")


# ============================================================================
# WebSocket Message Models
# ============================================================================

class WSMessage(BaseModel):
    """Base model for all WebSocket messages."""
    type: str = Field(..., description="Message type discriminator")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Message timestamp")
    data: Optional[Any] = Field(None, description="Generic payload")


class StdoutMessage(WSMessage):
    """Message containing standard output from a process."""
    type: Literal["stdout"] = "stdout"
    data: str = Field(..., description="Text content")
    raw: Optional[str] = Field(None, description="Raw content with ANSI codes")


class StderrMessage(WSMessage):
    """Message containing standard error from a process."""
    type: Literal["stderr"] = "stderr"
    data: str = Field(..., description="Text content")
    raw: Optional[str] = Field(None, description="Raw content with ANSI codes")


class ProgressMessage(WSMessage):
    """Message indicating progress of a long-running task."""
    type: Literal["progress"] = "progress"
    current: int = Field(..., description="Current progress value")
    total: int = Field(..., description="Total progress value")
    message: Optional[str] = Field(None, description="Progress description")


class InputRequestMessage(WSMessage):
    """Message requesting input from the client."""
    type: Literal["input_request"] = "input_request"
    prompt: str = Field(..., description="Prompt text to display")
    password: bool = Field(False, description="Whether input should be masked")


class CompleteMessage(WSMessage):
    """Message indicating job completion."""
    type: Literal["complete"] = "complete"
    success: bool = Field(..., description="Whether the job succeeded")
    result: Optional[Dict[str, Any]] = Field(None, description="Result data")
    cost: float = Field(0.0, description="Total cost incurred")


class FileChangeMessage(WSMessage):
    """Message indicating a file system event."""
    type: Literal["file_change"] = "file_change"
    path: str = Field(..., description="Path of the changed file")
    event: Literal["created", "modified", "deleted"] = Field(..., description="Type of change")


# ============================================================================
# Server Configuration Models
# ============================================================================

class ServerStatus(BaseModel):
    """General status information about the server."""
    version: str = Field(..., description="Server version")
    project_root: str = Field(..., description="Absolute path to project root")
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    active_jobs: int = Field(0, description="Number of currently running jobs")
    connected_clients: int = Field(0, description="Number of active WebSocket connections")


class ServerConfig(BaseModel):
    """Configuration settings for the server instance."""
    host: str = Field("127.0.0.1", description="Bind host")
    port: int = Field(9876, description="Bind port")
    token: Optional[str] = Field(None, description="Authentication token if enabled")
    allow_remote: bool = Field(False, description="Allow remote connections")
    allowed_origins: Optional[List[str]] = Field(None, description="CORS allowed origins")
    log_level: str = Field("info", description="Logging level")


# ============================================================================
# Remote Session Models
# ============================================================================

class RemoteSessionInfo(BaseModel):
    """Information about the current server's remote session registration."""
    session_id: Optional[str] = Field(None, description="Session ID if registered")
    cloud_url: Optional[str] = Field(None, description="Cloud access URL (e.g., https://pdd.dev/connect/{session_id})")
    registered: bool = Field(False, description="Whether session is registered with cloud")
    registered_at: Optional[datetime] = Field(None, description="When session was registered")


class SessionListItem(BaseModel):
    """Session item for list display."""
    session_id: str = Field(..., description="Unique session identifier")
    cloud_url: str = Field(..., description="Cloud access URL for remote access")
    project_name: str = Field(..., description="Project directory name")
    created_at: datetime = Field(..., description="When session was created")
    last_heartbeat: datetime = Field(..., description="Last heartbeat timestamp")
    status: Literal["active", "stale"] = Field(..., description="Session status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
# ============================================================================
# Context Audit Models
# ============================================================================

class TokenBreakdown(BaseModel):
    """Breakdown of tokens by category."""
    body: int = Field(0, description="Tokens from the main prompt body")
    includes: int = Field(0, description="Tokens from included files")
    tests: int = Field(0, description="Tokens from associated test files")
    examples: int = Field(0, description="Tokens from associated example files")
    grounding: int = Field(0, description="Tokens from grounding context")


class CostEstimate(BaseModel):
    """Cost estimation for prompt generation."""
    input_cost: float = Field(..., description="Estimated cost in currency")
    model: str = Field(..., description="Model name used for estimation")
    tokens: int = Field(..., description="Number of tokens")
    cost_per_million: float = Field(..., description="Cost per million tokens")
    currency: str = Field("USD", description="Currency code")


class TokenMetrics(BaseModel):
    """Comprehensive token metrics."""
    token_count: int = Field(..., description="Total number of hydrated tokens")
    context_limit: Optional[int] = Field(None, description="Model's input context limit")
    context_usage_percent: Optional[float] = Field(None, description="Percentage of context window used")
    cost_estimate: Optional[CostEstimate] = Field(None, description="Cost estimation details")
    breakdown: Optional[TokenBreakdown] = Field(None, description="Detailed token breakdown")


class ContextAudit(BaseModel):
    """Context window audit for a single prompt."""
    prompt_path: str = Field(..., description="Path to the prompt file")
    tree_hash: str = Field(..., description="Deterministic hash of the prompt and its dependencies")
    metrics: TokenMetrics = Field(..., description="Token metrics for the prompt")


class ContextAuditResponse(BaseModel):
    """Response for a project-wide context audit."""
    modules: Dict[str, ContextAudit] = Field(..., description="Mapping of prompt filename to audit data")


# ============================================================================
# Architecture Models
# ============================================================================

class ArchitectureModule(BaseModel):
    """Schema for an architecture module."""
    reason: str = Field(..., description="The architectural reason for this module")
    description: str = Field(..., description="Brief description of the module's purpose")
    dependencies: List[str] = Field(..., description="List of prompt filenames this module depends on")
    priority: int = Field(..., description="Processing priority for sync operations")
    filename: str = Field(..., description="The prompt filename (e.g., 'llm_invoke_python.prompt')")
    filepath: str = Field(..., description="The path to the generated code file")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    interface: Optional[Dict[str, Any]] = Field(None, description="The <pdd-interface> definition")
    group: Optional[str] = Field(None, description="Logical grouping for UI layout")


class ValidationError(BaseModel):
    """Validation error that blocks saving."""
    type: str = Field(..., description="Error type (e.g., circular_dependency)")
    message: str = Field(..., description="Human-readable error message")
    modules: List[str] = Field(..., description="Affected module filenames")


class ValidationWarning(BaseModel):
    """Validation warning that is informational only."""
    type: str = Field(..., description="Warning type (e.g., orphan_module)")
    message: str = Field(..., description="Human-readable warning message")
    modules: List[str] = Field(..., description="Affected module filenames")


class ValidateArchitectureRequest(BaseModel):
    """Request body for architecture validation."""
    modules: List[ArchitectureModule] = Field(..., description="Full list of architecture modules")


class ValidationResult(BaseModel):
    """Result of architecture validation."""
    valid: bool = Field(..., description="True if no errors (warnings are OK)")
    errors: List[ValidationError] = Field(..., description="Blocking validation errors")
    warnings: List[ValidationWarning] = Field(..., description="Informational warnings")


class SyncRequest(BaseModel):
    """Request body for sync-from-prompts operation."""
    filenames: Optional[List[str]] = Field(None, description="Specific prompts to sync, or null for all")
    dry_run: bool = Field(False, description="If true, validates changes without writing to disk")


class SyncResult(BaseModel):
    """Result of sync-from-prompts operation."""
    success: bool = Field(..., description="True if operation completed and validation passed")
    updated_count: int = Field(..., description="Number of modules successfully updated")
    skipped_count: int = Field(0, description="Number of modules skipped")
    results: List[Dict[str, Any]] = Field(..., description="Per-file sync results")
    validation: ValidationResult = Field(..., description="Validation status of the resulting architecture")
    errors: List[str] = Field(default_factory=list, description="Operation-level errors")


class GenerateTagsRequest(BaseModel):
    """Request body for generate-tags-for-prompt operation."""
    prompt_filename: str = Field(..., description="The filename of the prompt (e.g., 'llm_invoke_python.prompt')")


class GenerateTagsResult(BaseModel):
    """Result of generate-tags-for-prompt operation."""
    success: bool = Field(..., description="Whether generation succeeded")
    tags: Optional[str] = Field(None, description="The generated XML tag block")
    has_existing_tags: bool = Field(False, description="True if the prompt already had PDD tags")
    architecture_entry: Optional[Dict[str, Any]] = Field(None, description="The full architecture entry")
    error: Optional[str] = Field(None, description="Error message if failed")


class RearrangeRequest(BaseModel):
    """Request body for agentic graph layout rearrangement."""
    architecture_path: str = Field("architecture.json", description="Path relative to project root")


class RearrangeResult(BaseModel):
    """Result of agentic graph rearrangement."""
    success: bool = Field(..., description="Whether rearrangement succeeded")
    modules: Optional[List[Dict[str, Any]]] = Field(None, description="The updated modules list with new positions")
    message: Optional[str] = Field(None, description="Agent's summary of changes")
    error: Optional[str] = Field(None, description="Error message if failed")
