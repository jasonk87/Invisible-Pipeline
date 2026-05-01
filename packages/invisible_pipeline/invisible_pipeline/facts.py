import subprocess


def command_fact(command: list[str], cwd: str | None = None, timeout: int = 60) -> str:
    rendered_command = " ".join(command)
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )
        exit_code = result.returncode
        stdout = result.stdout or ""
        stderr = result.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = -1
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        stderr = f"TIMEOUT after {timeout}s\n{stderr}".strip()

    return (
        f"COMMAND:\n{rendered_command}\n\n"
        f"EXIT_CODE:\n{exit_code}\n\n"
        f"STDOUT:\n{stdout}\n\n"
        f"STDERR:\n{stderr}"
    )
