import sys
import traceback
import warnings
from pathlib import Path

WORKSPACE = Path("/workspace")
SCRIPT = WORKSPACE / "main.py"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def exit_status(stop: SystemExit) -> int:
    if stop.code is None:
        return 0
    if isinstance(stop.code, int):
        return stop.code
    print(stop.code, file=sys.stderr)
    return 1


def run_script() -> int:
    code = compile(SCRIPT.read_text(), "main.py", "exec")
    try:
        exec(code, {"__name__": "__main__"})
    except SystemExit as stop:
        return exit_status(stop)
    except BaseException as error:
        traceback.print_exception(type(error), error, error.__traceback__.tb_next)
        return 1
    return 0


def wrote_images() -> bool:
    return any(path.suffix.lower() in IMAGE_SUFFIXES for path in WORKSPACE.iterdir())


def save_open_figures() -> None:
    pyplot = sys.modules.get("matplotlib.pyplot")
    if pyplot is None or wrote_images():
        return
    for number in pyplot.get_fignums():
        figure = pyplot.figure(number)
        figure.savefig(WORKSPACE / f"figure_{number}.png", dpi=110, bbox_inches="tight")


def main() -> int:
    warnings.filterwarnings("ignore", message=".*non-interactive.*")
    status = run_script()
    try:
        save_open_figures()
    except Exception:
        traceback.print_exc()
    return status


if __name__ == "__main__":
    sys.exit(main())
