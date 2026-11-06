# tests/test_package.py
from __future__ import annotations

from email.parser import Parser
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from zipfile import ZipFile

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(
    args: list[str], *, cwd: Path, success: bool = True
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if success:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="session")
def wheels(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    artifacts = tmp_path_factory.mktemp("artifacts")
    direct = artifacts / "direct"
    rebuilt = artifacts / "from-sdist"
    _run(
        ["uv", "build", "--no-sources", "--wheel", "--out-dir", str(direct)],
        cwd=_REPO_ROOT,
    )
    _run(
        ["uv", "build", "--no-sources", "--sdist", "--out-dir", str(artifacts)],
        cwd=_REPO_ROOT,
    )
    (sdist,) = artifacts.glob("*.tar.gz")
    _run(
        [
            "uv",
            "build",
            "--no-sources",
            "--wheel",
            str(sdist),
            "--out-dir",
            str(rebuilt),
        ],
        cwd=artifacts,
    )

    expected = {
        "nox_tach/" + path.name
        for path in (_REPO_ROOT / "src/nox_tach").iterdir()
        if path.suffix == ".py" or path.name == "py.typed"
    }
    assert "nox_tach/py.typed" in expected
    with tarfile.open(sdist) as archive:
        names = {
            "/".join(name.split("/")[2:])
            for name in archive.getnames()
            if "/src/" in name
        }
        assert expected <= names

    result = (next(direct.glob("*.whl")), next(rebuilt.glob("*.whl")))
    for wheel in result:
        with ZipFile(wheel) as archive:
            assert expected <= set(archive.namelist())
            assert not any(
                name.startswith(("tests/", "tools/")) for name in archive.namelist()
            )
            (metadata_path,) = (
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            metadata = Parser().parsestr(archive.read(metadata_path).decode())
            assert metadata["Name"] == "nox-tach"
            assert metadata["Version"] == "0.1.0"
            assert set(metadata["Requires-Python"].split(",")) == {">=3.14.10", "<3.15"}
            assert metadata.get_all("Requires-Dist", []) == []
    return result


def _consumer(root: Path, names: tuple[str, str, str]) -> tuple[Path, Path, Path]:
    package = root / "src/pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    tach, policy, pyproject = (root / name for name in names)
    tach.write_text(
        'source_roots = ["src"]\nexact = true\nroot_module = "forbid"\n'
        '\n[[modules]]\npath = "pkg"\ndepends_on = []\n',
        encoding="utf-8",
    )
    policy.write_text(
        '[[modules]]\npath = "pkg"\ndependency_whitelist = []\n'
        "external_lib_whitelist = []\n",
        encoding="utf-8",
    )
    pyproject.write_text(
        '[tool.ruff.lint.isort]\nknown-first-party = ["stale"]\n',
        encoding="utf-8",
    )
    return tach, policy, pyproject


@pytest.mark.parametrize("from_sdist", [False, True], ids=["wheel", "sdist-wheel"])
def test_installed_artifacts(
    wheels: tuple[Path, Path],
    tmp_path: Path,
    from_sdist: bool,
) -> None:
    wheel = wheels[1 if from_sdist else 0]
    environment = tmp_path / "installed"
    _run(["uv", "venv", "--python", sys.executable, str(environment)], cwd=tmp_path)
    python = str(environment / "bin/python")
    cli = str(environment / "bin/nox-tach")
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        cwd=tmp_path,
    )

    # Explicit paths include spaces and are outside the current working directory.
    files = _consumer(
        tmp_path / "consumer config", ("graph.toml", "rules.toml", "project.toml")
    )
    options = [
        "--tach-path",
        str(files[0]),
        "--policy-path",
        str(files[1]),
        "--pyproject-path",
        str(files[2]),
    ]
    before = tuple(path.read_bytes() for path in files)
    failure = _run([cli, "--check", *options], cwd=tmp_path, success=False)
    assert str(files[0]) in failure.stderr
    assert str(files[1]) in failure.stderr
    assert str(files[2]) in failure.stderr
    assert "nox-tach --fix" in failure.stderr
    assert tuple(path.read_bytes() for path in files) == before
    _run([cli, "--fix", *options], cwd=tmp_path)
    normalized = tuple(path.read_bytes() for path in files)
    _run([python, "-I", "-m", "nox_tach", "--fix", *options], cwd=tmp_path)
    assert tuple(path.read_bytes() for path in files) == normalized
    _run([python, "-I", "-m", "nox_tach", "--check", *options], cwd=tmp_path)
    assert tuple(path.read_bytes() for path in files) == normalized

    for modes in ([], ["--check", "--fix"]):
        _run([cli, *modes, *options], cwd=tmp_path, success=False)
    files[1].write_text('[[modules]]\npath = "undeclared"\n', encoding="utf-8")
    invalid = tuple(path.read_bytes() for path in files)
    _run([cli, "--fix", *options], cwd=tmp_path, success=False)
    assert tuple(path.read_bytes() for path in files) == invalid
    files[1].write_text(
        '[[modules]]\npath = "pkg"\ntest_root = false\n', encoding="utf-8"
    )
    _run([cli, "--check", *options], cwd=tmp_path, success=False)

    defaults = tmp_path / "defaults"
    _consumer(defaults, ("tach.toml", "nox_tach.toml", "pyproject.toml"))
    _run([python, "-I", "-m", "nox_tach", "--fix"], cwd=defaults)
    _run([cli, "--check"], cwd=defaults)

    api = tmp_path / "api.py"
    api.write_text(
        "from pathlib import Path\n"
        "import nox_tach\n"
        "from nox_tach.config import (PolicyConfig, ModulePolicy, TestRootSpec, "
        "load_policy_config, parse_policy_config)\n"
        "from nox_tach.tach_config import (TachConfig, TachModuleSpec, "
        "parse_tach_config)\n"
        "assert nox_tach.__file__ is not None\n"
        f"assert Path(nox_tach.__file__).is_relative_to(Path({str(environment)!r}))\n"
        "policy: PolicyConfig = load_policy_config()\n"
        'assert policy == parse_policy_config(Path("nox_tach.toml").read_text())\n'
        "module: ModulePolicy = policy.modules[0]\n"
        'assert module.path == "pkg"\n'
        'root: TestRootSpec = TestRootSpec(path="specs", '
        'mirror_component_suffix="_spec")\n'
        'assert root.path == "specs"\n'
        'tach: TachConfig = parse_tach_config(Path("tach.toml").read_text())\n'
        "spec: TachModuleSpec = tach.modules[0]\n"
        'assert spec.path == "pkg"\n',
        encoding="utf-8",
    )
    _run([python, "-I", str(api)], cwd=defaults)
    # Resolve types from the clean install, including the packaged py.typed marker.
    pyright_config = tmp_path / "pyrightconfig.json"
    pyright_config.write_text(
        '{"typeCheckingMode": "strict", "pythonVersion": "3.14"}', encoding="utf-8"
    )
    _run(
        [
            str(Path(sys.executable).parent / "pyright"),
            "--project",
            str(pyright_config),
            "--pythonpath",
            python,
            str(api),
        ],
        cwd=tmp_path,
    )
