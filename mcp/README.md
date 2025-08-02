# VibeTeam MCP Server

This directory contains the Model Context Protocol (MCP) server implementation for VibeTeam, providing access to AI-powered coding agents through a standard protocol.

## Overview

The VibeTeam MCP server exposes the following capabilities:
- **Claude Code Agent**: AI-powered software engineering assistant
- **Engineering Manager**: Multi-agent coordination for complex projects
- **Task Automation**: Automated task completion from markdown files

## Server Modes

### 1. Standard MCP Mode (Default)
Uses stdio (stdin/stdout) for communication, compatible with MCP clients:
```bash
vibeteam-mcp
```

This mode accepts tasks as input parameters rather than reading from filesystem,
making it suitable for integration with any MCP client.

### 2. TCP Mode
Legacy TCP socket mode for backward compatibility:
```bash
vibeteam-mcp --tcp
# or
MCP_MODE=tcp vibeteam-mcp
```

## Available Tools

### execute_task
Execute a software engineering task using Claude Code Agent.
```json
{
  "name": "execute_task",
  "arguments": {
    "description": "Implement a binary search function in Python",
    "working_directory": "/path/to/project"  // optional
  }
}
```

### review_code
Review code for quality, bugs, and improvements.
```json
{
  "name": "review_code",
  "arguments": {
    "code": "def add(a, b):\n    return a + b",
    "language": "python",
    "context": "This is a utility function"  // optional
  }
}
```

### generate_code
Generate code based on specifications.
```json
{
  "name": "generate_code",
  "arguments": {
    "specification": "Create a REST API endpoint for user authentication",
    "language": "python",
    "style_guide": "PEP 8"  // optional
  }
}
```

### fix_code
Fix bugs or issues in code.
```json
{
  "name": "fix_code",
  "arguments": {
    "code": "def divide(a, b):\n    return a / b",
    "error_message": "ZeroDivisionError when b is 0",
    "language": "python"
  }
}
```

### write_tests
Write unit tests for code.
```json
{
  "name": "write_tests",
  "arguments": {
    "code": "def multiply(a, b):\n    return a * b",
    "language": "python",
    "test_framework": "pytest"
  }
}
```

### complete_tasks
Complete an array of tasks sequentially.
```json
{
  "name": "complete_tasks",
  "arguments": {
    "tasks": [
      "Implement user authentication",
      "Add password reset functionality",
      "Write unit tests for auth module"
    ],
    "max_tasks": 2  // optional, defaults to all
  }
}
```

### vibeteam_task_workflow
Execute the full vibeteam-task workflow (complete task, test, fix issues, optionally commit).
```json
{
  "name": "vibeteam_task_workflow",
  "arguments": {
    "tasks": [
      "[ ] Implement user authentication",
      "[ ] Add password reset functionality",
      "[x] Setup project structure"  // Will be skipped (already done)
    ],
    "auto_commit": true  // optional, defaults to false
  }
}
```

### manage_project
Use Engineering Manager to coordinate multiple agents on a project.
```json
{
  "name": "manage_project",
  "arguments": {
    "project_description": "Build a web scraper with data analysis features",
    "team_size": 3  // optional, defaults to 2
  }
}
```

## Available Resources

### workspace:///
Lists all files in the current working directory.

### workspace:///tasks.md
Reads the current tasks.md file if it exists.

### agent:///status
Shows the current status of VibeTeam agents.

## Environment Variables

- `VIBETEAM_WORKING_DIR`: Set the working directory for agents (defaults to current directory)
- `MCP_MODE`: Set to "tcp" to use TCP socket mode instead of stdio
- `MCP_PORT`: Port for TCP mode (defaults to 8080)
- `MCP_DEBUG`: Set to enable debug logging to stderr

## Public Access via Cloudflare

To expose your MCP server publicly:

1. Run the Cloudflare setup script:
   ```bash
   ./deploy/cloudflare/setup_tunnel.sh
   ```

2. Follow the prompts to configure your tunnel

3. Your MCP server will be accessible at `https://your-subdomain.your-domain.com`

See [deploy/cloudflare/README.md](../deploy/cloudflare/README.md) for detailed instructions.

## Testing

Run the comprehensive test suite:
```bash
pytest tests/mcp/test_vibeteam_mcp_server.py -v
pytest tests/mcp/test_mcp_command.py -v
```

## Architecture

The MCP implementation consists of:

1. **stdio_server.py**: Core MCP protocol implementation using stdin/stdout
2. **vibeteam_mcp_server.py**: VibeTeam-specific tools and resources
3. **base_mcp_server.py**: Legacy TCP socket implementation
4. **software_engineer_server.py**: Legacy Software Engineer MCP server
5. **engineering_manager_server.py**: Legacy Engineering Manager MCP server

The new implementation (stdio_server + vibeteam_mcp_server) follows the official MCP specification and is compatible with standard MCP clients.