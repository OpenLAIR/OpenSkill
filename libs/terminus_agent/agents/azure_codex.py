"""Codex wrapper that routes API calls through Azure AI Foundry.

Codex CLI uses WebSocket/HTTP to connect to OpenAI. Simply setting
OPENAI_BASE_URL is not enough — the CLI reads provider configuration
from $CODEX_HOME/config.toml.  This subclass injects a config.toml
that defines an "azure" model provider pointing at the Azure AI
Foundry endpoint, so all Codex requests are routed correctly.

Register in AGENT_IMPORT_PATHS as:
    "codex": "libs.terminus_agent.agents.azure_codex:AzureCodex"
"""

from __future__ import annotations

import os
import shlex

from harbor.agents.installed.base import ExecInput
from harbor.agents.installed.codex import Codex
from harbor.models.trial.paths import EnvironmentPaths


class AzureCodex(Codex):
    """Codex subclass that routes requests through Azure AI Foundry."""

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        escaped_instruction = shlex.quote(instruction)

        if not self.model_name:
            raise ValueError("Model name is required")

        model = self.model_name.split("/")[-1]  # "openai/gpt-5.4" -> "gpt-5.4"

        azure_base_url = os.environ.get(
            "OPENAI_BASE_URL",
            os.environ.get("OPENAI_API_BASE", ""),
        )

        env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "CODEX_HOME": EnvironmentPaths.agent_dir.as_posix(),
        }

        # Build reasoning flag
        reasoning_effort = self._reasoning_effort
        reasoning_flag = (
            f"-c model_reasoning_effort={reasoning_effort} "
            if reasoning_effort
            else ""
        )

        # Command 0: write auth.json AND config.toml for Azure provider
        # auth.json: heredoc WITHOUT quotes so ${OPENAI_API_KEY} is expanded by bash
        # config.toml: values baked in at Python time (no shell expansion needed)
        setup_command = (
            'cat >"$CODEX_HOME/auth.json" <<AUTHEOF\n'
            '{\n'
            '  "OPENAI_API_KEY": "${OPENAI_API_KEY}"\n'
            '}\n'
            'AUTHEOF\n'
            '\n'
            'cat >"$CODEX_HOME/config.toml" <<\'TOMLEOF\'\n'
            f'model = "{model}"\n'
            'model_provider = "azure"\n'
            '\n'
            '[model_providers.azure]\n'
            'name = "Azure AI Foundry"\n'
            f'base_url = "{azure_base_url}"\n'
            'env_key = "OPENAI_API_KEY"\n'
            'wire_api = "responses"\n'
            'TOMLEOF\n'
        )

        # Command 1: run codex exec (same as parent, but without --model
        # since config.toml already sets it via model_provider)
        run_command = (
            "codex exec "
            "--dangerously-bypass-approvals-and-sandbox "
            "--skip-git-repo-check "
            f"--model {model} "
            "--json "
            "--enable unified_exec "
            f"{reasoning_flag}"
            "-- "
            f"{escaped_instruction} "
            f"2>&1 </dev/null | tee "
            f"{EnvironmentPaths.agent_dir / self._OUTPUT_FILENAME} "
            "&& rm -rf $CODEX_HOME/auth.json"
        )

        return [
            ExecInput(command=setup_command, env=env),
            ExecInput(command=run_command, env=env),
        ]
