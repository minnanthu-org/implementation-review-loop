"""Provider utilities."""

from __future__ import annotations

import shutil

from agent_loop.core.repo_config import WorkflowProvider

# CLI executable name for each provider.
PROVIDER_CLI_MAP: dict[WorkflowProvider, str] = {
    WorkflowProvider.CODEX: "codex",
    WorkflowProvider.CLAUDE: "claude",
    WorkflowProvider.GEMINI: "gemini",
}


class ProviderNotAvailableError(RuntimeError):
    """Raised when a provider CLI is not found on PATH."""

    def __init__(self, provider: WorkflowProvider, cli_name: str) -> None:
        self.provider = provider
        self.cli_name = cli_name
        super().__init__(
            f"Provider '{provider.value}' requires the '{cli_name}' CLI, "
            f"but it was not found on PATH. "
            f"Please install it before using --provider {provider.value}."
        )


def check_provider_available(provider: WorkflowProvider) -> str:
    """Verify that the CLI for *provider* exists on PATH.

    Returns the resolved path to the CLI executable.
    Raises :class:`ProviderNotAvailableError` if not found.
    """
    cli_name = PROVIDER_CLI_MAP[provider]
    resolved = shutil.which(cli_name)
    if resolved is None:
        raise ProviderNotAvailableError(provider, cli_name)
    return resolved


def is_provider_available(provider: WorkflowProvider) -> tuple[bool, str]:
    """Check provider availability without raising.

    Returns ``(True, path)`` or ``(False, cli_name)``.
    """
    cli_name = PROVIDER_CLI_MAP[provider]
    resolved = shutil.which(cli_name)
    if resolved is not None:
        return True, resolved
    return False, cli_name
