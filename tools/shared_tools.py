from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root, e.g. 'main.py' or 'utils/helpers.py'.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete file contents to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Edit an existing file by replacing a unique string with new content. "
                "Use this for targeted fixes instead of rewriting the whole file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root.",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "The exact string to find and replace. Must appear exactly once in the file.",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "The replacement string.",
                    },
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the workspace. Use for installing packages, running code, inspecting output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute.",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root.",
                    },
                },
                "required": ["path"],
            },
        },
    },
]


def execute_tool_call(
    name: str,
    arguments: dict,
    container_id: str,
    sandbox,
    code_files: dict,
) -> tuple[str, dict]:
    if name == "write_file":
        path = arguments.get("path", "unknown.py")
        content = arguments.get("content", "")
        sandbox.write_file(container_id, path, content)
        code_files[path] = content
        return f"File written: {path} ({len(content)} chars)", code_files

    elif name == "edit_file":
        path = arguments.get("path", "")
        old_str = arguments.get("old_str", "")
        new_str = arguments.get("new_str", "")

        current = sandbox.read_file(container_id, path)
        if current is None:
            return f"Error: file '{path}' not found.", code_files

        count = current.count(old_str)
        if count == 0:
            return f"Error: old_str not found in '{path}'.", code_files
        if count > 1:
            return (
                f"Error: old_str appears {count} times in '{path}'. "
                "It must be unique. Include more surrounding context.",
                code_files,
            )

        updated = current.replace(old_str, new_str, 1)
        sandbox.write_file(container_id, path, updated)
        code_files[path] = updated
        return f"File edited: {path}", code_files

    elif name == "bash":
        command = arguments.get("command", "echo 'no command'")
        exit_code, stdout, stderr = sandbox.exec_command(container_id, command)
        result = f"$ {command}\nexit_code: {exit_code}"
        if stdout.strip():
            result += f"\nstdout:\n{stdout[:1500]}"
        if stderr.strip():
            result += f"\nstderr:\n{stderr[:1500]}"
        return result, code_files

    elif name == "read_file":
        path = arguments.get("path", "")
        content = sandbox.read_file(container_id, path)
        if content is None:
            return f"Error: file '{path}' not found.", code_files
        return f"Contents of {path}:\n{content[:3000]}", code_files

    else:
        return f"Unknown tool: {name}", code_files
