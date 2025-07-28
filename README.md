# AI Vibe Team

![](./doc/ai-agent.gif)

While building Vibe Browser, I prototyped a self-organizing development team composed entirely of AI agents. Here’s how it works:

Coding Agents (e.g. Claude Code, Codex, Gemini CLI) generate and test code around the clock.

Analysis Agents ingest logs, UI screenshots, and test results, then flag broken or suboptimal areas.

AI Engineering Manager (powered by a premium LLM like o3, Gemini 2.5-Pro, or Claude 4-Opus) reflects on the coding agents’ output, prioritizes fixes and features, and issues new tasks—ensuring we never ship “it compiles” as “it’s done.”

Iteration Loop continues autonomously, with the manager refining requirements and the coding agents executing them until the feature is production-ready.

This architecture lets us spin up a full “dev team” in minutes, with the quality-control layer of a senior engineering manager baked in. It’s already speeding up Vibe Browser’s feature cycle—and could redefine how small teams (or even solo founders) scale every aspect of software development.


A CLI-based multi-agent coding tool that uses AI to automate software development tasks through collaborative AI agents.

## 🚀 Features

- **AI-Powered Team**: Engineering Manager orchestrates specialized coding agents
- **Task Automation**: From simple scripts to full applications
- **Real-Time Collaboration**: Interactive CLI with progress tracking
- **Smart Testing**: Comprehensive test suite with real LLM integration
- **Extensible**: Plugin architecture for adding new agents and tools

## 📦 Installation

### Option 1: Install from GitHub (Recommended)

```bash
pip install git+https://github.com/VibeTechnologies/VibeTeam.git
```

### Option 2: Development Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/VibeTechnologies/VibeTeam.git
   cd VibeTeam
   ```

2. **Install in development mode**:
   ```bash
   pip install -e .
   # or for development with extra dependencies:
   pip install -e .[dev]
   ```

## ⚡ Quick Start

1. **Set API keys** (required for Claude Code functionality):
   ```bash
   export ANTHROPIC_API_KEY="your-anthropic-key"
   ```

2. **Run the automated task system**:
   ```bash
   vibeteam-task
   ```

3. **Or use the interactive CLI**:
   ```bash
   vibeteam-cli
   ```

### Available Commands

After installation, you'll have access to these commands:

- **`vibeteam-task`** - Automated task completion from tasks.md
- **`vibeteam-cli`** - Interactive multi-agent coding interface  
- **`vibeteam-mcp`** - MCP server for ChatGPT/Claude integration

## 🤖 VibeCode Tasks - Automated Task Completion

The `vibeteam-task` command automatically reads tasks from `tasks.md` and completes them using Claude Code agents.

### Usage

1. **Create a tasks.md file** with checkbox-style tasks:
   ```markdown
   [ ] Write python hello world hello.py.
   [ ] Simple html page hello world hello.html.
   [ ] Create a REST API endpoint for user registration.
   ```

2. **Run the automated task completion**:
   ```bash
   vibeteam-task
   ```

   Or specify a different directory:
   ```bash
   vibeteam-task --dir /path/to/your/project
   ```

The system will:
- Read uncompleted tasks from `tasks.md`
- Use Claude Code agent to complete each task
- Create files, write tests, run tests, and fix issues
- Mark tasks as completed in `tasks.md`
- Commit changes to git

### Features

- ✅ **Automatic Task Detection**: Reads `[ ]` unchecked tasks from `tasks.md`
- ✅ **Full Development Cycle**: Creates code, tests, runs tests, fixes issues
- ✅ **Git Integration**: Reviews changes and commits completed work
- ✅ **Error Handling**: Retries and fixes issues automatically
- ✅ **Progress Tracking**: Updates `tasks.md` with completed tasks `[x]`

## 🛠 Usage

### Interactive Mode
```bash
python -m cli.main_cli start
```

### Execute a Single Task
```bash
python -m cli.main_cli execute "Create a REST API with FastAPI and SQLAlchemy"
```

## 🧪 Testing

Run all tests:
```bash
pytest tests/
```

Run specific test categories:
```bash
# Unit tests
pytest tests/unit

# Integration tests (requires API keys)
pytest tests/integration

# Performance tests
pytest tests/performance
```

## 🏗 Architecture

### Core Components
- **Engineering Manager**: Orchestrates tasks using LiteLLM
- **Claude Code Agent**: Executes coding tasks with Claude
- **CLI Interface**: Rich terminal interface for interaction
- **Test Suite**: Comprehensive tests with real LLM integration

## 📚 Documentation

- [Testing Guide](TESTING.md): How to run and write tests
- [API Reference](docs/API.md): Detailed API documentation
- [Development Guide](docs/DEVELOPMENT.md): Contributing to the project

4. **Agent Registry** (`agents/agent_registry.py`)
   - Manages agent registration and discovery
   - Provides capability-based agent lookup
   - Handles agent lifecycle management

5. **CLI Interface** (`cli/`)
   - Interactive team management interface
   - Progress tracking and status display
   - Configuration management

### Workflow

1. **Task Input**: User provides a high-level coding task
2. **Decomposition**: Engineering Manager breaks task into subtasks
3. **Assignment**: Subtasks are assigned to appropriate coding agents
4. **Execution**: Agents execute their assigned subtasks
5. **Review**: Engineering Manager reviews completed work
6. **Feedback**: Revision requests are sent if needed
7. **Integration**: Results are compiled into final output

## Configuration

### Configuration File (`team_config.json`)
```json
{
  "default_model": "gpt-4",
  "claude_model": "claude-3-sonnet-20240229",
  "default_agents": 2,
  "working_directory": "/path/to/project",
  "max_task_time": 3600,
  "retry_attempts": 3,
  "log_level": "INFO"
}
```

### Environment Variables
- `TEAM_DEFAULT_MODEL`: Model for Engineering Manager
- `TEAM_CLAUDE_MODEL`: Model for Claude coding agents
- `TEAM_DEFAULT_AGENTS`: Number of coding agents to spawn
- `TEAM_WORKING_DIR`: Default working directory
- `TEAM_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Command Reference

### Main Commands
- `start`: Launch interactive team interface
- `execute <task>`: Execute single task and exit
- `configure`: Interactive configuration setup
- `status`: Show team status (for persistent sessions)

### Interactive Commands
- `task <description>`: Execute a coding task
- `status`: Show current team status
- `agents`: List all registered agents
- `history`: Show recent task history
- `help`: Show available commands
- `quit`: Exit the interface

### Options
- `--working-dir, -w`: Set working directory
- `--model, -m`: Set Engineering Manager model
- `--claude-model`: Set Claude agent model
- `--agents, -a`: Number of coding agents
- `--verbose, -v`: Enable verbose output
- `--output, -o`: Output file for results

## Development

### Project Structure
```
ai-coding-supervisor/
├── agents/                 # Agent implementations
│   ├── base_agent.py      # Abstract base agent
│   ├── engineering_manager.py  # Main orchestrator
│   ├── claude_code_agent.py    # Claude coding agent
│   └── agent_registry.py       # Agent management
├── cli/                   # CLI interface
│   ├── main_cli.py       # Main CLI commands
│   └── interface.py      # Interactive interface
├── utils/                # Utilities
│   ├── logging.py        # Logging setup
│   └── config.py         # Configuration management
├── tests/                # Test files
├── tasks.md             # Technical task breakdown
├── requirements.txt     # Dependencies
└── team_coding_tool.py  # Main entry point
```

### Adding New Agents
1. Inherit from `BaseAgent`
2. Implement required methods (`execute_task`, `review_work`)
3. Register capabilities in constructor
4. Register with `AgentRegistry`

### Extending Functionality
- Add new agent capabilities in `AgentCapability` enum
- Implement custom task decomposition strategies
- Add new CLI commands in `main_cli.py`
- Extend configuration options in `config.py`

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure claude-code-sdk-python is properly installed
2. **API Key Issues**: Set required environment variables for LiteLLM and Claude
3. **Permission Errors**: Check file permissions in working directory
4. **Model Access**: Verify API keys and model availability

### Debug Mode
Enable verbose logging:
```bash
python team_coding_tool.py start --verbose
```

### Logs
Check log files in the `logs/` directory for detailed execution information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Acknowledgments

- Built on top of claude-code-sdk-python
- Uses LiteLLM for multi-model support
- Rich library for beautiful CLI interfaces
