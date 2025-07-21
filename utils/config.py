"""
Configuration utilities for the multi-agent coding tool
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


DEFAULT_CONFIG = {
    "default_model": "gpt-4",
    "claude_model": "claude-3-sonnet-20240229",
    "default_agents": 2,
    "working_directory": None,
    "max_task_time": 3600,
    "retry_attempts": 3,
    "log_level": "INFO",
    "auto_approve_safe_commands": False,
    "max_subtasks": 10,
    "task_timeout": 1800
}


def load_config(config_file: str = "team_config.json") -> Dict[str, Any]:
    """Load configuration from file"""
    config_path = Path(config_file)
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Merge with defaults
            merged_config = DEFAULT_CONFIG.copy()
            merged_config.update(config)
            return merged_config
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load config file {config_file}: {e}")
            return DEFAULT_CONFIG.copy()
    
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any], config_file: str = "team_config.json") -> bool:
    """Save configuration to file"""
    try:
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return True
        
    except IOError as e:
        print(f"Error: Could not save config file {config_file}: {e}")
        return False


def get_env_config() -> Dict[str, Any]:
    """Get configuration from environment variables"""
    env_config = {}
    
    # Map environment variables to config keys
    env_mapping = {
        "TEAM_DEFAULT_MODEL": "default_model",
        "TEAM_CLAUDE_MODEL": "claude_model", 
        "TEAM_DEFAULT_AGENTS": "default_agents",
        "TEAM_WORKING_DIR": "working_directory",
        "TEAM_LOG_LEVEL": "log_level",
        "TEAM_MAX_TASK_TIME": "max_task_time",
        "TEAM_RETRY_ATTEMPTS": "retry_attempts"
    }
    
    for env_var, config_key in env_mapping.items():
        value = os.getenv(env_var)
        if value is not None:
            # Convert numeric values
            if config_key in ["default_agents", "max_task_time", "retry_attempts"]:
                try:
                    env_config[config_key] = int(value)
                except ValueError:
                    pass
            # Convert boolean values
            elif config_key in ["auto_approve_safe_commands"]:
                env_config[config_key] = value.lower() in ("true", "1", "yes", "on")
            else:
                env_config[config_key] = value
    
    return env_config


def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple configuration dictionaries"""
    merged = {}
    
    for config in configs:
        if config:
            merged.update(config)
    
    return merged
