# ai_providers/base.py
from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def get_ai_action(self, history: list, context: str, thinking_enabled: bool) -> (str, str):
        pass

    @abstractmethod
    def get_verifier_verdict(self, verifier_history: list, task: str, sandbox_state: str) -> dict:
        pass

    @abstractmethod
    def get_taskmaster_task(self, taskmaster_history: list, history_summary: str) -> dict:
        pass
