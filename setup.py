#!/usr/bin/env python3
"""
Setup script for VibeTeam - AI-powered multi-agent coding tool.
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "AI-powered multi-agent coding tool with automated task completion."

# Read requirements from requirements.txt
def read_requirements():
    req_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    requirements = []
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    requirements.append(line)
    return requirements

setup(
    name="vibeteam",
    version="0.1.0",
    author="VibeTeam",
    author_email="team@vibetech.co",
    description="AI-powered multi-agent coding tool with automated task completion",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/VibeTechnologies/VibeTeam",
    packages=find_packages(exclude=['tests*', 'docs*', 'deploy*']),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black",
            "flake8",
            "mypy",
        ],
        "mcp": [
            "uvicorn[standard]",
            "fastapi",
        ],
    },
    entry_points={
        "console_scripts": [
            "vibeteam-task=vibecode_tasks:main",
            "vibeteam-cli=cli.main_cli:main",
            "vibeteam-mcp=run_mcp_server:main_console",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml", "*.json"],
    },
    keywords="ai coding automation cli multi-agent development",
    project_urls={
        "Bug Reports": "https://github.com/VibeTechnologies/VibeTeam/issues",
        "Source": "https://github.com/VibeTechnologies/VibeTeam",
        "Documentation": "https://github.com/VibeTechnologies/VibeTeam#readme",
    },
)
