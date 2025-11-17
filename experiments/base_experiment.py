# experiments/base_experiment.py
from abc import ABC, abstractmethod


class BaseExperiment(ABC):
    @abstractmethod
    def run(self, ai_provider, model_name, rate_limiter, network_enabled, log_filename):
        pass
