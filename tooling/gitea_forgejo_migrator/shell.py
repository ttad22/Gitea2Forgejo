from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass


@dataclass(slots=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class ShellRunner:
    def __init__(self, ssh_target: str | None = None) -> None:
        self.ssh_target = ssh_target

    def run(self, command: str) -> CommandResult:
        if self.ssh_target:
            argv = ["ssh", self.ssh_target, "bash", "-lc", command]
        else:
            argv = ["bash", "-lc", command]
        proc = subprocess.run(argv, capture_output=True, text=True)
        return CommandResult(proc.stdout, proc.stderr, proc.returncode)

    def check(self, command: str) -> str:
        result = self.run(command)
        if result.returncode != 0:
            raise RuntimeError(
                f"command failed ({result.returncode}): {command}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result.stdout.strip()
