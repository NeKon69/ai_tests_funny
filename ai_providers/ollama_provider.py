# ai_providers/ollama_provider.py
import ollama
from ai_providers.base import AIProvider
from utils import parse_ai_json_response, parse_verifier_response, parse_taskmaster_response
from config import MAX_QUOTA_RETRIES
import time


class OllamaProvider(AIProvider):
    def __init__(self, model_name):
        self.model_name = model_name

    def get_ai_action(self, history: list, context: str, thinking_enabled: bool) -> (str, str):
        history.append({"role": "user", "content": context})
        retry_count = 0
        while retry_count < MAX_QUOTA_RETRIES:
            try:
                response = ollama.chat(model=self.model_name, messages=history)
                ai_full_response = response["message"]["content"]
                history.append({"role": "assistant", "content": ai_full_response})
                return parse_ai_json_response(ai_full_response)
            except Exception as e:
                retry_count += 1
                print(f"\n[UNEXPECTED ERROR] ⚠️ {type(e).__name__}: {e}")
                if retry_count < MAX_QUOTA_RETRIES:
                    print(f"[UNEXPECTED ERROR] Attempt {retry_count}/{MAX_QUOTA_RETRIES}")
                    print(f"[UNEXPECTED ERROR] ⏳ Waiting 30 seconds before retry...")
                    time.sleep(30)
                    print(f"[RETRY] 🔄 Retrying request...")
                    continue
                else:
                    return (
                        f"Error communicating with AI API after {MAX_QUOTA_RETRIES} attempts: {e}",
                        "",
                    )
        return "Error: Maximum retry attempts exceeded.", ""

    def get_verifier_verdict(self, verifier_history: list, task: str, sandbox_state: str) -> dict:
        context = f"""
TASK TO VERIFY:
{task}

CURRENT SANDBOX STATE:
{sandbox_state}

Analyze whether the task was completed successfully and provide your verdict as JSON.
"""
        verifier_history.append({"role": "user", "content": context})
        retry_count = 0
        while retry_count < MAX_QUOTA_RETRIES:
            try:
                response = ollama.chat(model=self.model_name, messages=verifier_history)
                ai_full_response = response["message"]["content"]
                verifier_history.append({"role": "assistant", "content": ai_full_response})
                return parse_verifier_response(ai_full_response)
            except Exception as e:
                retry_count += 1
                if retry_count < MAX_QUOTA_RETRIES:
                    time.sleep(30)
                    continue
                else:
                    return {
                        "success": False,
                        "feedback": f"Verifier error: {e}",
                        "completion_percentage": 0,
                    }
        return {
            "success": False,
            "feedback": "Verifier timeout",
            "completion_percentage": 0,
        }

    def get_taskmaster_task(self, taskmaster_history: list, history_summary: str) -> dict:
        from prompts import TASKMASTER_PROMPT_BASE
        context = TASKMASTER_PROMPT_BASE.replace("{history}", history_summary)
        taskmaster_history.append({"role": "user", "content": context})
        retry_count = 0
        while retry_count < MAX_QUOTA_RETRIES:
            try:
                response = ollama.chat(model=self.model_name, messages=taskmaster_history)
                ai_full_response = response["message"]["content"]
                taskmaster_history.append({"role": "assistant", "content": ai_full_response})
                return parse_taskmaster_response(ai_full_response)
            except Exception as e:
                retry_count += 1
                if retry_count < MAX_QUOTA_RETRIES:
                    time.sleep(30)
                    continue
                else:
                    return None
        return None
