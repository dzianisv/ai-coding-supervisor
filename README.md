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

1. **Set API keys** (required for AI functionality):
   ```bash
   # For Claude Code functionality (primary)
   export ANTHROPIC_API_KEY="your-anthropic-key"
   
   # For OpenAI reflection and analysis (optional)
   export OPENAI_API_KEY="your-openai-key"
   export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional, for custom endpoints
   ```

2. **Run the automated task system**:
   ```bash
   vibeteam-task
   ```

3. **Use with reflection (enhanced quality)**:
   ```bash
   vibeteam-task --enable-reflection --debug
   ```

4. **Run the MCP server** (for ChatGPT/Claude integration):
   ```bash
   vibeteam-mcp
   ```

### Available Commands

After installation, you'll have access to these commands:

- **`vibeteam-task`** - Automated task completion from tasks.md with optional OpenAI reflection
- **`vibeteam-cli`** - Interactive multi-agent coding interface  
- **`vibeteam-mcp`** - Model Context Protocol (MCP) server for ChatGPT/Claude integration

### Command Options

```bash
# Basic task automation
vibeteam-task

# Task automation with OpenAI reflection (enhanced quality)
vibeteam-task --enable-reflection --debug

# Custom directory and tasks file
vibeteam-task --dir /path/to/project --tasks-file my-tasks.md

# MCP server
vibeteam-mcp                    # Standard MCP protocol (stdio)
```

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
- Optionally use OpenAI for reflection and quality analysis

### Features

- ✅ **Automatic Task Detection**: Reads `[ ]` unchecked tasks from `tasks.md`
- ✅ **Full Development Cycle**: Creates code, tests, runs tests, fixes issues
- ✅ **Git Integration**: Reviews changes and commits completed work
- ✅ **Error Handling**: Retries and fixes issues automatically
- ✅ **Progress Tracking**: Updates `tasks.md` with completed tasks `[x]`
- ✅ **OpenAI Reflection**: Optional quality analysis and improvement suggestions
- ✅ **MCP Server**: Standard Model Context Protocol for ChatGPT/Claude integration
- ✅ **Deployment Ready**: Docker, Cloudflare Tunnel, Kubernetes support

## 🌐 MCP Server (Model Context Protocol)

VibeTeam includes a full MCP server implementation that exposes AI coding capabilities to ChatGPT, Claude, and other MCP clients.

### Available Tools
- `execute_task` - Execute coding tasks with Claude Code Agent
- `review_code` - Review code for quality and improvements  
- `generate_code` - Generate code from specifications
- `fix_code` - Fix bugs and issues in code
- `write_tests` - Create unit tests for code
- `complete_tasks` - Complete tasks from tasks.md
- `manage_project` - Use Engineering Manager for coordination

### Deployment Options

1. **Local Development**:
   ```bash
   vibeteam-mcp  # Standard MCP protocol
   ```

2. **Public Access via Cloudflare**:
   ```bash
   ./deploy/cloudflare/setup_tunnel.sh
   ```

3. **Docker Deployment**:
   ```bash
   docker build -t vibeteam .
   docker run -p 8080:8080 vibeteam
   ```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

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
# Core functionality tests
pytest tests/test_*.py

# MCP server tests
pytest tests/mcp/

# Cloudflare tunnel tests
pytest tests/tunnel/
```

**Note**: Some tests require API keys to be set. Tests are automatically run via GitHub Actions on push/PR.

## 🏗 Architecture

### Core Components
- **Claude Code Agent**: Primary coding agent using Anthropic Claude via claude-code-sdk
- **Engineering Manager**: Task orchestration and quality control
- **MCP Server**: Standard Model Context Protocol implementation for external AI integration
- **Task Automation**: File-based task management with `tasks.md`
- **Reflection Module**: Optional OpenAI-powered quality analysis and improvement suggestions
- **Deployment Infrastructure**: Docker, Cloudflare Tunnel, Kubernetes support

### Project Structure
```
VibeTeam/
├── agents/                 # Agent implementations
│   ├── claude_code_agent.py    # Primary coding agent
│   ├── engineering_manager.py  # Task orchestration
│   └── base_agent.py          # Base agent class
├── mcp/                   # Model Context Protocol server
│   ├── vibeteam_mcp_server.py  # Main MCP implementation
│   └── stdio_server.py         # Standard MCP protocol
├── cli/                   # Command-line interface
├── tests/                 # Comprehensive test suite
├── deploy/                # Deployment configurations
│   ├── cloudflare/           # Cloudflare Tunnel setup
│   ├── k8s/                  # Kubernetes manifests
│   └── local/               # Local development
└── vibeteam_tasks.py      # Main task automation script
```

### Workflow

1. **Task Input**: Create tasks in `tasks.md` with checkbox format `[ ] Task description`
2. **Execution**: Run `vibeteam-task` to automatically process unchecked tasks
3. **AI Processing**: Claude Code Agent analyzes task and generates solution
4. **Quality Control**: Optional OpenAI reflection provides analysis and suggestions
5. **Testing**: Automatically creates and runs tests for generated code
6. **Git Integration**: Reviews changes and commits completed work
7. **Task Completion**: Marks tasks as done `[x]` in `tasks.md`

## 📚 Documentation

- [Deployment Guide](DEPLOYMENT.md): Complete deployment options and setup
- [MCP Server Guide](mcp/README.md): Model Context Protocol implementation details
- [Testing Guide](TESTING.md): How to run and write tests
- [GitHub Actions](.github/workflows/): Automated CI/CD workflows

## Configuration

### Environment Variables

**Required:**
```bash
ANTHROPIC_API_KEY="your-anthropic-key"    # For Claude Code Agent
```

**Optional:**
```bash
OPENAI_API_KEY="your-openai-key"          # For reflection analysis
OPENAI_BASE_URL="https://api.openai.com/v1"  # Custom OpenAI endpoint
VIBETEAM_WORKING_DIR="/path/to/project"   # Default working directory
```

## Troubleshooting

### Common Issues

1. **API Key Missing**: Set `ANTHROPIC_API_KEY` environment variable
2. **Task Timeout**: Tasks may take several minutes to complete
3. **Git Issues**: Ensure git is configured and working directory is a git repo
4. **Test Failures**: Some tests require internet access and API keys

### Debug Mode
Enable detailed logging:
```bash
vibeteam-task --debug
```

### Logs
- MCP server logs: `vibeteam-mcp.log`
- Task execution logs: `mcp_server.log`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with claude-code-sdk-python for AI agent functionality
- Model Context Protocol (MCP) for standardized AI integration
- OpenAI API for reflection and quality analysis
- Docker and Cloudflare for deployment infrastructure
