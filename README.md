# 🧑‍⚖️ Mini-Judge
<p align="center">
<a href="https://github.com/yourusername/mini-judge"><img src="https://img.shields.io/badge/Mini-Judge-blue.svg"></a>
<a href="https://github.com/yourusername/mini-judge/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
<a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json"></a>
<a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>

</p>
<p align="center">
<a href="#-about">📖 About</a> •
<a href="#-installation">📦 Installation</a> •
<a href="#-quick-start">🚀 Quick Start</a> •
<a href="#-development">🛠 Development</a> •
<a href="#-roadmap">🛣 Roadmap</a>
</p>

## 📖 About

Mini-Judge is a lightweight, high-performance online judge system for evaluating code solutions, supporting multiple programming languages and evaluation modes.

> [!Warning]
> Just a toy project.

## 📦 Installation

option 1: conda

```bash
conda create -n evalhub python=3.11 -y
conda activate evalhub

pip install -r requirements.txt
pip install -e .
```

option 2: uv

```bash
uv venv --python 3.11
source .venv/bin/activate

uv pip install -r requirements.txt
uv pip install -e .
```

> [!Note]
> [uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

## 🚀 Quick Start

Start the server

```bash
uvicorn app.main:app --reload
```

Submit a code for evaluation

```bash
curl -X POST http://localhost:8000/api/v1/judge \
  -H "Content-Type: application/json" \
  -d '{"code": "print('Hello, World!')", "language": "python"}'
```

Check results

```bash
curl http://localhost:8000/api/v1/judge/{task_id}
```

## 🛠 Development

### Code Quality Tools

> [!Note]
> We use [Ruff](https://github.com/astral-sh/ruff) as our Python linter and formatter.

```bash
# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Pre-commit Hooks

> [!Note]
> Pre-commit hooks automatically check your code before committing.

```bash
# Installation
pre-commit install

# Run all checks manually
pre-commit run --all-files
```

## 🛣 Roadmap

- [ ] high concurrency

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
