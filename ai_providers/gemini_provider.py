# ai_providers/gemini_provider.py
import os
import time
import requests
from ai_providers.base import AIProvider
from utils import parse_ai_json_response, parse_verifier_response, parse_taskmaster_response, extract_retry_delay
from config import MAX_QUOTA_RETRIES


class GeminiProvider(AIProvider):
    def __init__(self, model_name):
        self.model_name = model_name

    def get_ai_action(self, history: list, context: str, thinking_enabled: bool) -> (str, str):
        history.append({"role": "user", "content": context})
        retry_count = 0
        while retry_count < MAX_QUOTA_RETRIES:
            try:
                gemini_contents = []
                for msg in history:
                    role = "user" if msg["role"] in ["user", "system"] else "model"
                    gemini_contents.append(
                        {"role": role, "parts": [{"text": msg["content"]}]}
                    )

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
                headers = {
                    "x-goog-api-key": os.getenv("GOOGLE_API_KEY"),
                    "Content-Type": "application/json",
                }

                payload = {
                    "contents": gemini_contents,
                    "safetySettings": [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_NONE",
                        },
                    ],
                    "generationConfig": {
                        "candidateCount": 1,
                        "thinkingConfig": {
                            "thinkingBudget": -1 if thinking_enabled else 0,
                            "includeThoughts": thinking_enabled,
                        },
                    },
                }

                response = requests.post(
                    url, headers=headers, json=payload, timeout=120
                )
                response_data = response.json()

                if isinstance(response_data, dict) and "error" in response_data:
                    error_code = response_data["error"].get("code", "unknown")
                    error_status = response_data["error"].get("status", "UNKNOWN")
                    error_message = response_data["error"].get(
                        "message", "Unknown error"
                    )

                    retry_count += 1

                    if error_code == 429:
                        retry_delay = extract_retry_delay(response_data)
                        print(
                            f"\n[API ERROR 429] 🚨 Quota exceeded! Attempt {retry_count}/{MAX_QUOTA_RETRIES}"
                        )
                        print(
                            f"[API ERROR 429] ⏳ Waiting {retry_delay:.1f} seconds..."
                        )
                        time.sleep(retry_delay)
                    else:
                        print(
                            f"\n[API ERROR {error_code}] 🚨 {error_status}: {error_message}"
                        )
                        print(
                            f"[API ERROR {error_code}] Attempt {retry_count}/{MAX_QUOTA_RETRIES}"
                        )
                        print(
                            f"[API ERROR {error_code}] ⏳ Waiting 30 seconds before retry..."
                        )
                        time.sleep(30)

                    if retry_count < MAX_QUOTA_RETRIES:
                        print(
                            f"[RETRY] 🔄 Retrying request (attempt {retry_count + 1})..."
                        )
                        continue
                    else:
                        return (
                            f"Error: API failed after {MAX_QUOTA_RETRIES} attempts. Last error: [{error_code}] {error_message}",
                            "",
                        )

                if (
                    "candidates" in response_data
                    and len(response_data["candidates"]) > 0
                ):
                    parts = response_data["candidates"][0]["content"]["parts"]
                    full_text = ""
                    thoughts_text = ""

                    for part in parts:
                        if "text" in part:
                            if part.get("thought", False):
                                thoughts_text += part["text"] + "\n"
                            else:
                                full_text += part["text"]

                    ai_full_response = full_text
                    if thoughts_text and thinking_enabled:
                        print(f"\n💭 [THINKING] {thoughts_text.strip()}\n")
                else:
                    raise Exception(f"API error: {response_data}")

                history.append({"role": "assistant", "content": ai_full_response})
                return parse_ai_json_response(ai_full_response)

            except requests.exceptions.RequestException as e:
                retry_count += 1
                print(f"\n[NETWORK ERROR] ❌ Request failed: {e}")
                if retry_count < MAX_QUOTA_RETRIES:
                    print(f"[NETWORK ERROR] Attempt {retry_count}/{MAX_QUOTA_RETRIES}")
                    print(f"[NETWORK ERROR] ⏳ Waiting 30 seconds before retry...")
                    time.sleep(30)
                    print(f"[RETRY] 🔄 Retrying request...")
                    continue
                else:
                    return (
                        f"Error: Network failed after {MAX_QUOTA_RETRIES} attempts: {e}",
                        "",
                    )
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
                gemini_contents = []
                for msg in verifier_history:
                    role = "user" if msg["role"] in ["user", "system"] else "model"
                    gemini_contents.append(
                        {"role": role, "parts": [{"text": msg["content"]}]}
                    )

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
                headers = {
                    "x-goog-api-key": os.getenv("GOOGLE_API_KEY"),
                    "Content-Type": "application/json",
                }

                payload = {
                    "contents": gemini_contents,
                    "safetySettings": [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_NONE",
                        },
                    ],
                    "generationConfig": {"candidateCount": 1},
                }

                response = requests.post(
                    url, headers=headers, json=payload, timeout=120
                )
                response_data = response.json()

                if isinstance(response_data, dict) and "error" in response_data:
                    retry_count += 1
                    if retry_count < MAX_QUOTA_RETRIES:
                        time.sleep(30)
                        continue
                    else:
                        return {
                            "success": False,
                            "feedback": "Verifier API failed",
                            "completion_percentage": 0,
                        }

                if (
                    "candidates" in response_data
                    and len(response_data["candidates"]) > 0
                ):
                    parts = response_data["candidates"][0]["content"]["parts"]
                    ai_full_response = "".join([part.get("text", "") for part in parts])
                else:
                    raise Exception(f"API error: {response_data}")

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
                gemini_contents = []
                for msg in taskmaster_history:
                    role = "user" if msg["role"] in ["user", "system"] else "model"
                    gemini_contents.append(
                        {"role": role, "parts": [{"text": msg["content"]}]}
                    )

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
                headers = {
                    "x-goog-api-key": os.getenv("GOOGLE_API_KEY"),
                    "Content-Type": "application/json",
                }

                payload = {
                    "contents": gemini_contents,
                    "safetySettings": [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_NONE",
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_NONE",
                        },
                    ],
                    "generationConfig": {"candidateCount": 1},
                }

                response = requests.post(
                    url, headers=headers, json=payload, timeout=120
                )
                response_data = response.json()

                if isinstance(response_data, dict) and "error" in response_data:
                    retry_count += 1
                    if retry_count < MAX_QUOTA_RETRIES:
                        time.sleep(30)
                        continue
                    else:
                        return None

                if (
                    "candidates" in response_data
                    and len(response_data["candidates"]) > 0
                ):
                    parts = response_data["candidates"][0]["content"]["parts"]
                    ai_full_response = "".join([part.get("text", "") for part in parts])
                else:
                    raise Exception(f"API error: {response_data}")

                taskmaster_history.append(
                    {"role": "assistant", "content": ai_full_response}
                )
                return parse_taskmaster_response(ai_full_response)

            except Exception as e:
                retry_count += 1
                if retry_count < MAX_QUOTA_RETRIES:
                    time.sleep(30)
                    continue
                else:
                    return None
        return None
