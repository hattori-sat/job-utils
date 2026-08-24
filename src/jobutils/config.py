"""Load and validate the small non-secret workspace configuration profile."""

from pathlib import Path
from typing import Any, Dict, List, Optional


class ConfigError(ValueError):
    """A workspace configuration cannot be parsed safely."""


def _scalar(value: str) -> Any:
    value = value.strip()
    if value in ("null", "~"):
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def load_config(path: Path) -> Dict[str, Any]:
    """Load the supported two-level YAML profile without third-party packages."""

    path = Path(path)
    if not path.is_file():
        raise ConfigError("configuration file was not found: {}".format(path))
    result: Dict[str, Any] = {}
    section: Optional[str] = None
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            raise ConfigError("invalid configuration line {}".format(line_number))
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not key:
            raise ConfigError("empty configuration key on line {}".format(line_number))
        if indent == 0 and not raw_value.strip():
            section = key
            result[section] = {}
            continue
        if indent == 0:
            result[key] = _scalar(raw_value)
            section = None
            continue
        if section is None or not isinstance(result.get(section), dict):
            raise ConfigError(
                "nested key without a section on line {}".format(line_number)
            )
        result[section][key] = _scalar(raw_value)
    return result


def validate_config(path: Path) -> List[str]:
    """Return human-readable validation errors for a workspace profile."""

    try:
        config = load_config(path)
    except ConfigError as error:
        return [str(error)]
    errors: List[str] = []
    for section, keys in {
        "jira": ("base_url", "project", "issue_type", "email_env", "token_env"),
        "confluence": (
            "base_url",
            "space_id",
            "space_key",
            "parent_page_id",
            "email_env",
            "token_env",
        ),
    }.items():
        values = config.get(section)
        if not isinstance(values, dict):
            errors.append("missing section: {}".format(section))
            continue
        for key in keys:
            if values.get(key) in (None, ""):
                errors.append("missing {}.{}".format(section, key))
    if config.get("version") != 1:
        errors.append("version must be 1")
    return errors
