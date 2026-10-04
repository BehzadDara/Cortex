import time
from collections.abc import Callable
from dataclasses import dataclass

from app.rag.code_sandbox import DockerCodeSandbox, ExecutionResult


@dataclass
class Case:
    name: str
    code: str
    expect: Callable[[ExecutionResult], bool]


def file_names(result: ExecutionResult) -> set[str]:
    return {file.name for file in result.files}


def failed_with(message: str) -> Callable[[ExecutionResult], bool]:
    return lambda result: result.exit_code != 0 and message in result.stderr


CASES = [
    Case("prints output", "print(sum(range(101)))", lambda r: r.stdout.strip() == "5050"),
    Case(
        "captures an open chart",
        "import matplotlib.pyplot as plt\nplt.plot([1, 3, 2])\nplt.show()",
        lambda r: file_names(r) == {"figure_1.png"},
    ),
    Case(
        "keeps a saved chart without duplicating it",
        "import matplotlib.pyplot as plt\nplt.plot([1, 2])\nplt.savefig('chart.png')",
        lambda r: file_names(r) == {"chart.png"},
    ),
    Case(
        "returns a written data file",
        "import pandas as pd\npd.DataFrame({'a': [1]}).to_csv('data.csv')",
        lambda r: file_names(r) == {"data.csv"},
    ),
    Case(
        "reports a traceback from the script",
        "x = 1\nprint(x / 0)",
        lambda r: 'File "main.py", line 2' in r.stderr and "ZeroDivisionError" in r.stderr,
    ),
    Case(
        "has no network",
        "import urllib.request\nurllib.request.urlopen('http://1.1.1.1', timeout=3)",
        failed_with("Network is unreachable"),
    ),
    Case(
        "cannot write outside the workspace",
        "open('/etc/evil', 'w').write('x')",
        failed_with("Read-only file system"),
    ),
    Case(
        "survives a fork bomb",
        "import os\nwhile True:\n    os.fork()",
        lambda r: r.exit_code != 0 and not r.timed_out,
    ),
    Case(
        "stops a memory bomb",
        "blocks = []\nwhile True:\n    blocks.append(bytearray(50_000_000))",
        failed_with("memory limit"),
    ),
    Case("stops an infinite loop", "while True:\n    pass", lambda r: r.timed_out),
    Case(
        "never follows a symlink out",
        "import os\nos.symlink('/etc/passwd', 'leak.txt')",
        lambda r: not r.files,
    ),
    Case(
        "drops disallowed file types",
        "open('page.html', 'w').write('<script>alert(1)</script>')",
        lambda r: not r.files,
    ),
    Case(
        "truncates a flood of output",
        "while True:\n    print('x' * 1000)",
        lambda r: r.timed_out or "output truncated" in r.stdout,
    ),
]


def main() -> None:
    sandbox = DockerCodeSandbox()
    passed = 0
    for case in CASES:
        started = time.perf_counter()
        result = sandbox.run(case.code)
        elapsed = time.perf_counter() - started
        ok = case.expect(result)
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {elapsed:5.1f}s  {case.name}")
    print(f"contained: {passed}/{len(CASES)}")


if __name__ == "__main__":
    main()
