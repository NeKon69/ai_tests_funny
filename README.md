# AI Sandbox

This project provides a sandboxed environment for running AI experiments. It is designed to be modular and extensible, allowing for the easy addition of new AI providers, experiments, and tools.

## Core Concepts

*   **AI Providers**: These are modules that interface with different AI APIs (e.g., Ollama, Gemini). They are responsible for sending requests and parsing responses.
*   **Experiments**: These are different modes of operation for the AI sandbox. Each experiment defines a specific scenario or task for the AI agents.
*   **Sandbox**: A Docker container that provides an isolated environment for the AI agents to run commands.

## Setup

1.  **Install Docker**: Make sure Docker is installed and running on your system.
2.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Build the Docker image**:
    ```bash
    docker build -t ai-sandbox-duel .
    ```
4.  **Set up AI provider credentials**:
    *   For **Gemini**, set the `GOOGLE_API_KEY` environment variable.

## Usage

Run the main script to start an experiment:

```bash
python main.py
```

You will be prompted to choose an experiment mode, AI provider, and other settings.

### Experiment Modes

*   **Duel Mode**: Two AI agents, Ghost and Guardian, compete against each other in a sandboxed environment. Ghost tries to "escape" the sandbox by creating a specific file, while Guardian tries to prevent it.
*   **Game Loop Mode**: An AI agent called Coder tries to solve programming tasks in the sandbox. Another agent, Verifier, checks the solution, and a third agent, Taskmaster, generates new tasks based on Coder's performance.

## Extending the Project

### Adding a new AI Provider

1.  Create a new file in the `ai_providers` directory (e.g., `my_provider.py`).
2.  Create a new class that inherits from `AIProvider` (in `ai_providers/base.py`).
3.  Implement the `get_ai_action`, `get_verifier_verdict`, and `get_taskmaster_task` methods.
4.  Update `main.py` to include your new provider as an option.

### Adding a new Experiment

1.  Create a new file in the `experiments` directory (e.g., `my_experiment.py`).
2.  Create a new class that inherits from `BaseExperiment` (in `experiments/base_experiment.py`).
3.  Implement the `run` method.
4.  Update `main.py` to include your new experiment as an option.