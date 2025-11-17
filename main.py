# main.py
import os
import sys
from utils import RateLimiter
from ai_providers.ollama_provider import OllamaProvider
from ai_providers.gemini_provider import GeminiProvider
from experiments.duel_mode import DuelMode
from experiments.game_loop_mode import GameLoopMode
from sandbox import cleanup_sandbox

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def main():
    print("=" * 60)
    print("   AI SANDBOX ORCHESTRATOR")
    print("=" * 60)

    # Mode selection
    print("\n📊 SELECT MODE:")
    print("[1] DUEL MODE - Ghost vs Guardian (two AIs fight)")
    print("[2] GAME LOOP MODE - Coder + Taskmaster + Verifier (autonomous learning)")

    while True:
        mode_choice = input("\nChoose mode (1 or 2): ")
        if mode_choice in ["1", "2"]:
            break
        print("Invalid choice. Please enter 1 or 2.")

    # AI Provider Setup
    print("\n--- AI Provider Setup ---")
    ai_provider, model_name = "", ""
    rpm_limit = 0

    while True:
        provider_choice = input("Choose AI provider: [1] Ollama, [2] Gemini: ")
        if provider_choice == "1":
            model_name = input("Enter Ollama model name (e.g., llama3): ")
            ai_provider = OllamaProvider(model_name)
            break
        elif provider_choice == "2":
            if not GEMINI_AVAILABLE:
                print(
                    "\n[ERROR] 'google-generativeai' not found. Run: pip install google-generativeai"
                )
                sys.exit(1)
            if not os.getenv("GOOGLE_API_KEY"):
                print(
                    "\n[ERROR] GOOGLE_API_KEY env var not set. Get a key from AI Studio and export it."
                )
                sys.exit(1)

            gemini_models = {
                "1": "gemini-1.5-pro-latest",
                "2": "gemini-1.5-flash-latest",
                "3": "gemini-1.0-pro",
            }
            rpm_limits = {
                "gemini-1.5-pro-latest": 2,
                "gemini-1.5-flash-latest": 10,
                "gemini-1.0-pro": 15,
            }
            while True:
                model_choice = input(
                    "Choose Gemini model: [1] 1.5 Pro, [2] 1.5 Flash, [3] 1.0 Pro: "
                )
                if model_choice in gemini_models:
                    model_name = gemini_models[model_choice]
                    rpm_limit = rpm_limits.get(model_name, 15)
                    ai_provider = GeminiProvider(model_name)
                    break
                else:
                    print("Invalid choice.")
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")

    rate_limiter = RateLimiter(rpm_limit)

    # Experiment settings
    if mode_choice == "1":
        while True:
            try:
                max_turns_input = input(
                    "Enter the maximum number of turns for the duel: "
                )
                max_turns = int(max_turns_input)
                if max_turns > 0:
                    break
                else:
                    print("Please enter a positive number.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        while True:
            network_input = input(
                "Enable network access for this duel? (y/n): "
            ).lower()
            if network_input in ["y", "yes"]:
                network_enabled = True
                break
            elif network_input in ["n", "no"]:
                network_enabled = False
                break
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

        test_num = 1
        while os.path.exists(f"duel_test{test_num}.txt"):
            test_num += 1
        log_filename = f"duel_test{test_num}.txt"

        experiment = DuelMode(max_turns)
        experiment.run(ai_provider, model_name, rate_limiter, network_enabled, log_filename)

    else:  # mode_choice == "2"
        while True:
            try:
                max_cycles_input = input(
                    "Enter the maximum number of learning cycles: "
                )
                max_cycles = int(max_cycles_input)
                if max_cycles > 0:
                    break
                else:
                    print("Please enter a positive number.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        print("\n--- Initial Task Setup ---")
        print("Enter the first task for Coder (or press Enter for default):")
        print(
            "Default: 'Create a file /app/output.txt with the text \"Hello, World!\"'"
        )
        initial_task = input("Task: ").strip()

        if not initial_task:
            initial_task = "Create a file /app/output.txt with the text 'Hello, World!'"

        network_enabled = False

        test_num = 1
        while os.path.exists(f"gameloop_test{test_num}.txt"):
            test_num += 1
        log_filename = f"gameloop_test{test_num}.txt"

        experiment = GameLoopMode(max_cycles, initial_task)
        experiment.run(ai_provider, model_name, rate_limiter, network_enabled, log_filename)

    cleanup_sandbox()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[ORCHESTRATOR] Experiment interrupted by user.")
        cleanup_sandbox()
        sys.exit(0)
    except Exception as e:
        print(f"\n[ORCHESTRATOR] A critical error occurred: {e}")
        cleanup_sandbox()
        sys.exit(1)
