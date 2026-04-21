"""Lightweight logging helpers for the embedded code agents."""

from __future__ import annotations


def _log(agent_name: str, level: str, message: str) -> None:
    display = agent_name.replace("_", " ").title()
    print(f"[{display}] {level}: {message}")


def log_agent_start(agent_name: str, show_location: bool = True) -> None:
    _ = show_location
    _log(agent_name, "info", f"starting {agent_name}")


def log_agent_success(agent_name: str, message: str, show_location: bool = True) -> None:
    _ = show_location
    _log(agent_name, "success", message)


def log_agent_error(agent_name: str, message: str, show_location: bool = True) -> None:
    _ = show_location
    _log(agent_name, "error", message)


def log_agent_warning(agent_name: str, message: str, show_location: bool = True) -> None:
    _ = show_location
    _log(agent_name, "warning", message)


def log_agent_info(agent_name: str, message: str, show_location: bool = True) -> None:
    _ = show_location
    _log(agent_name, "info", message)

