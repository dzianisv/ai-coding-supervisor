# AI Coding Supervisor

A CLI-based multi-agent coding tool that uses AI to automate software development tasks through collaborative AI agents.

## 🚀 Features

- **AI-Powered Team**: Engineering Manager orchestrates specialized coding agents
- **Task Automation**: From simple scripts to full applications
- **Real-Time Collaboration**: Interactive CLI with progress tracking
- **Smart Testing**: Comprehensive test suite with real LLM integration
- **Extensible**: Plugin architecture for adding new agents and tools

## ⚡ Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set API keys** (optional, needed for cloud models):
   ```bash
   export ANTHROPIC_API_KEY="your-anthropic-key"
   export OPENAI_API_KEY="your-openai-key"
   ```

3. **Run the CLI**:
   ```bash
   python -m cli.main_cli
   ```

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
