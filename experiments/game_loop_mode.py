# experiments/game_loop_mode.py
import time
from experiments.base_experiment import BaseExperiment
from sandbox import prepare_sandbox, execute_in_docker, execute_as_root
from utils import log_and_print
from prompts import (
    CODER_PROMPT_BASE,
    VERIFIER_PROMPT_BASE,
    TASKMASTER_PROMPT_BASE,
    NETWORK_ENABLED_ADDON,
    NETWORK_DISABLED_ADDON,
)
from config import MAX_JSON_RETRIES


def handle_privileged_command(
    command: str, character_name: str, log_file, network_enabled: bool
) -> str:
    package_name, url, action_type, is_privileged, requires_network = (
        "",
        "",
        "",
        False,
        False,
    )
    stripped_command = command.strip()
    if stripped_command.startswith("apt-get") or stripped_command.startswith("apt "):
        action_type, is_privileged, requires_network = (
            "run a privileged apt command",
            True,
            True,
        )
        package_name = stripped_command
    elif stripped_command.startswith("curl") or stripped_command.startswith("wget"):
        action_type, is_privileged, requires_network = "download from", True, True
        parts = stripped_command.split()
        url = next(
            (part for part in parts if part.startswith("http")), "an unknown URL"
        )
    if not is_privileged:
        return execute_in_docker(command)
    if requires_network and not network_enabled:
        denial_message = (
            "[GATEKEEPER] Request DENIED. Network access is disabled for this session."
        )
        log_and_print(f"\n{denial_message}", log_file)
        return "STDOUT:\n\nSTDERR:\nGATEKEEPER: Your request was denied because network access is disabled."
    prompt_text = f"\n[GATEKEEPER] {character_name} wants to {action_type} '{package_name or url}'. Allow? (y/n): "
    log_and_print(prompt_text, log_file, end="")
    while True:
        decision = input().lower()
        if decision in ["y", "yes"]:
            log_and_print("y", log_file)
            log_and_print("[GATEKEEPER] Request APPROVED. Executing...", log_file)
            if action_type == "run a privileged apt command":
                return execute_as_root(command)
            else:
                return execute_in_docker(command)
        elif decision in ["n", "no"]:
            log_and_print("n", log_file)
            log_and_print("[GATEKEEPER] Request DENIED.", log_file)
            return "STDOUT:\n\nSTDERR:\nGATEKEEPER: Your request was denied by the operator."
        else:
            print("Invalid input. Please enter 'y' or 'n'.")


class GameLoopMode(BaseExperiment):
    def __init__(self, max_cycles, initial_task):
        self.max_cycles = max_cycles
        self.initial_task = initial_task

    def run(self, ai_provider, model_name, rate_limiter, network_enabled, log_filename):
        CODER_PROMPT = CODER_PROMPT_BASE + (
            NETWORK_DISABLED_ADDON if not network_enabled else NETWORK_ENABLED_ADDON
        )

        prepare_sandbox(network_enabled)
        time.sleep(2)

        # Create /app directory in the container
        execute_as_root("mkdir -p /app && chown sandboxuser:sandboxuser /app")

        with open(log_filename, "w", encoding="utf-8") as log_file:
            header = f"--- AI GAME LOOP: CODER + TASKMASTER + VERIFIER ---\nProvider: {ai_provider.__class__.__name__} | Model: {model_name} | Max Cycles: {self.max_cycles} | Network: {network_enabled}\nLogging to: {log_filename}\n"
            log_and_print(header, log_file)

            coder_history = [{"role": "system", "content": CODER_PROMPT}]
            taskmaster_history = [
                {
                    "role": "system",
                    "content": TASKMASTER_PROMPT_BASE.replace("{history}", ""),
                }
            ]
            verifier_history = [{"role": "system", "content": VERIFIER_PROMPT_BASE}]

            performance_history = []
            current_task = self.initial_task
            max_attempts = 10

            log_and_print(f"\n{'='*20} CYCLE 0 (INITIALIZATION) {'='*20}", log_file)
            log_and_print(f"📋 Initial Task: {current_task}", log_file)
            log_and_print(f"🎯 Max Attempts: {max_attempts}", log_file)

            for cycle in range(1, self.max_cycles + 1):
                cycle_header = f"\n{'='*25} CYCLE {cycle}/{self.max_cycles} {'='*25}"
                log_and_print(cycle_header, log_file)
                log_and_print(f"📋 Current Task: {current_task}", log_file)
                log_and_print(f"🎯 Max Attempts Allowed: {max_attempts}", log_file)

                attempts = 0
                task_solved = False
                coder_result = ""
                verifier_verdict = {}

                while attempts < max_attempts and not task_solved:
                    attempts += 1
                    log_and_print(
                        f"\n--- 🤖 CODER'S ATTEMPT #{attempts}/{max_attempts} ---",
                        log_file,
                    )

                    if attempts == 1:
                        context = f"Task: {current_task}\n\nProvide your solution as a JSON object with 'thoughts' and 'command'."
                    else:
                        context = f"Your previous attempt produced:\n{coder_result}\n\nVerifier feedback: {verifier_verdict.get('feedback', '')}\n\nTask is still not complete. Try a different approach. Provide your next solution as JSON."

                    retries = 0
                    while retries < MAX_JSON_RETRIES:
                        rate_limiter.wait()
                        coder_thoughts, coder_command = ai_provider.get_ai_action(
                            coder_history,
                            context,
                            thinking_enabled=(
                                ai_provider.__class__.__name__ == "GeminiProvider"
                            ),
                        )
                        rate_limiter.add_request()

                        if not coder_command and "Error:" in coder_thoughts:
                            retries += 1
                            log_and_print(
                                f"🤖 Coder's response was invalid. Retrying ({retries}/{MAX_JSON_RETRIES})...",
                                log_file,
                            )
                            context = "(user) Your previous response was not valid JSON. Review the format and try again."
                            if retries == MAX_JSON_RETRIES:
                                coder_command = "echo 'JSON formatting error'"
                                log_and_print(
                                    "🤖 Coder failed to produce valid JSON.", log_file
                                )
                        else:
                            break

                    log_and_print(f"💭 Coder's Thoughts: {coder_thoughts}", log_file)
                    log_and_print(f"⚡ Coder's Command: `{coder_command}`", log_file)

                    coder_result = handle_privileged_command(
                        coder_command, "Coder", log_file, network_enabled
                    )
                    log_and_print(f"🖥️  Result:\n{coder_result}", log_file)

                    sandbox_state = execute_in_docker(
                        "ls -la /app/ 2>/dev/null && echo '--- FILE CONTENTS ---' && find /app -type f -exec echo '=== {} ===' \\; -exec cat {} \\; 2>/dev/null"
                    )

                    log_and_print("\n--- 🔍 VERIFIER CHECKING ---", log_file)
                    rate_limiter.wait()
                    verifier_verdict = ai_provider.get_verifier_verdict(
                        verifier_history,
                        current_task,
                        sandbox_state,
                    )
                    rate_limiter.add_request()

                    log_and_print(
                        f"✅ Success: {verifier_verdict['success']}", log_file
                    )
                    log_and_print(
                        f"📊 Completion: {verifier_verdict['completion_percentage']}%",
                        log_file,
                    )
                    log_and_print(
                        f"💬 Feedback: {verifier_verdict['feedback']}", log_file
                    )

                    if verifier_verdict["success"]:
                        task_solved = True
                        break

                    time.sleep(0.5)

                attempt_percentage = (attempts / max_attempts) * 100
                performance_record = {
                    "cycle": cycle,
                    "task": current_task,
                    "attempts": attempts,
                    "max_attempts": max_attempts,
                    "attempt_percentage": attempt_percentage,
                    "solved": task_solved,
                    "completion_percentage": (
                        verifier_verdict.get("completion_percentage", 0)
                        if not task_solved
                        else 100
                    ),
                }
                performance_history.append(performance_record)

                history_summary = "PERFORMANCE HISTORY:\n"
                for i, record in enumerate(performance_history[-5:], 1):
                    status = "✅ SOLVED" if record["solved"] else "❌ FAILED"
                    history_summary += f"\nCycle {record['cycle']}: {status}\n"
                    history_summary += f"  Task: {record['task']}\n"
                    history_summary += f"  Attempts: {record['attempts']}/{record['max_attempts']} ({record['attempt_percentage']:.1f}%)\n"
                    history_summary += (
                        f"  Completion: {record['completion_percentage']}%\n"
                    )

                recent_success_rate = (
                    sum(1 for r in performance_history[-3:] if r["solved"])
                    / min(3, len(performance_history))
                    * 100
                )
                avg_attempt_percentage = sum(
                    r["attempt_percentage"] for r in performance_history[-3:]
                ) / min(3, len(performance_history))

                history_summary += f"\nRECENT STATISTICS (last 3 cycles):\n"
                history_summary += f"  Success rate: {recent_success_rate:.1f}%\n"
                history_summary += (
                    f"  Avg attempt usage: {avg_attempt_percentage:.1f}%\n"
                )

                if task_solved:
                    log_and_print(
                        f"\n🎉 Task SOLVED in {attempts}/{max_attempts} attempts ({attempt_percentage:.1f}%)!",
                        log_file,
                    )
                else:
                    log_and_print(
                        f"\n❌ Task FAILED after {attempts} attempts.", log_file
                    )

                log_and_print("\n--- 🎓 TASKMASTER GENERATING NEXT TASK ---", log_file)

                rate_limiter.wait()
                taskmaster_response = ai_provider.get_taskmaster_task(
                    taskmaster_history, history_summary
                )
                rate_limiter.add_request()

                if taskmaster_response is None:
                    log_and_print(
                        "⚠️ Taskmaster error. Using fallback task...", log_file
                    )
                    new_task = (
                        "Create a file /app/output.txt with the current timestamp"
                    )
                    max_attempts = 15
                else:
                    new_task = taskmaster_response["task"]
                    max_attempts = taskmaster_response["max_attempts"]
                    log_and_print(f"📝 Next Task: {new_task}", log_file)
                    log_and_print(
                        f"🎯 Difficulty: {taskmaster_response['expected_difficulty']}",
                        log_file,
                    )
                    log_and_print(f"🔢 Max Attempts: {max_attempts}", log_file)
                    log_and_print(
                        f"💡 Reasoning: {taskmaster_response['reasoning']}", log_file
                    )

                current_task = new_task
                execute_in_docker("rm -rf /app/*")
                time.sleep(1)

            game_over_header = f"\n{'='*28} TRAINING COMPLETE {'='*28}"
            log_and_print(game_over_header, log_file)
            log_and_print(f"🏁 Completed {self.max_cycles} training cycles.", log_file)

            total_solved = sum(1 for r in performance_history if r["solved"])
            success_rate = (total_solved / len(performance_history)) * 100
            log_and_print(f"\n📊 FINAL STATISTICS:", log_file)
            log_and_print(
                f"  Tasks solved: {total_solved}/{len(performance_history)} ({success_rate:.1f}%)",
                log_file,
            )
