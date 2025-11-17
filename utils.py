# utils.py
import json
import re
import time
from collections import deque


class RateLimiter:
    def __init__(self, rpm_limit):
        self.limit = rpm_limit if rpm_limit > 0 else float("inf")
        self.timestamps = deque()
        print(f"[RATE LIMITER] Initialized with a limit of {self.limit} RPM.")

    def wait(self):
        if self.limit == float("inf"):
            return

        now = time.monotonic()
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.limit:
            oldest_request_time = self.timestamps[0]
            time_to_wait = 60 - (now - oldest_request_time)
            if time_to_wait > 0:
                print(
                    f"\n[RATE LIMITER] RPM limit ({self.limit}) reached. Waiting for {time_to_wait:.1f} seconds..."
                )
                time.sleep(time_to_wait + 0.5)

    def add_request(self):
        if self.limit != float("inf"):
            self.timestamps.append(time.monotonic())


def log_and_print(message, file_handle, end="\n"):
    print(message, end=end)
    file_handle.write(message + end)
    file_handle.flush()


def parse_ai_json_response(response_text: str) -> (str, str):
    try:
        response_text = response_text.strip()
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not match:
            return "Error: Could not find a JSON object in the response.", ""

        data = json.loads(match.group(0))

        thoughts_raw = data.get("thoughts", "No 'thoughts' field provided.")
        if isinstance(thoughts_raw, dict):
            thoughts = "\n".join([f"{k}: {v}" for k, v in thoughts_raw.items()])
        elif isinstance(thoughts_raw, str):
            thoughts = thoughts_raw
        else:
            return (
                f"Error: 'thoughts' has unexpected type: {type(thoughts_raw).__name__}",
                "",
            )

        command = data.get("command", "")
        if not isinstance(command, str):
            return "Error: 'command' must be a string.", ""

        return thoughts, command
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON. {str(e)}", ""
    except Exception as e:
        return f"Unexpected error: {e}", ""


def parse_verifier_response(response_text: str) -> dict:
    try:
        response_text = response_text.strip()
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not match:
            return {
                "success": False,
                "feedback": "Error: Could not parse Verifier response",
                "completion_percentage": 0,
            }

        data = json.loads(match.group(0))

        return {
            "success": data.get("success", False),
            "feedback": data.get("feedback", "No feedback provided"),
            "completion_percentage": data.get("completion_percentage", 0),
        }
    except Exception as e:
        return {
            "success": False,
            "feedback": f"Verifier error: {e}",
            "completion_percentage": 0,
        }


def parse_taskmaster_response(response_text: str) -> dict:
    try:
        response_text = response_text.strip()
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group(0))

        return {
            "task": data.get("task", ""),
            "max_attempts": data.get("max_attempts", 20),
            "expected_difficulty": data.get("expected_difficulty", "medium"),
            "reasoning": data.get("reasoning", ""),
        }
    except Exception as e:
        print(f"[ERROR] Failed to parse Taskmaster response: {e}")
        return None


def extract_retry_delay(error_data: dict) -> float:
    try:
        if "error" in error_data and "details" in error_data["error"]:
            for detail in error_data["error"]["details"]:
                if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                    retry_delay_str = detail.get("retryDelay", "0s")
                    return float(retry_delay_str.replace("s", ""))
    except Exception as e:
        print(f"[WARNING] Failed to extract retry delay: {e}")
    return 30.0
