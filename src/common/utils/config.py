"""
Load configuration from `config.toml`.
"""

from pathlib import Path
from pydantic import BaseModel, field_validator

THIS_DIR = Path(__file__).parent.resolve()

CONFIG_FILE_PATH = THIS_DIR / "config.toml"


class Config(BaseModel):
    timeout_s: int
    reading_order_y_tolerance: int
    default_prefix: str
    bold_threshold: float  # (1 * 0.1 = 10% bolder than average)
    header_threshold: float
    footer_threshold: float
    small_text_threshold: float
    skip_patterns: list[str]
    header_thresholds: dict[int, float]

    @field_validator(
        "bold_threshold",
        "header_threshold",
        "footer_threshold",
        "small_text_threshold",
        mode="before",
    )
    def between_zero_and_one(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("Value must be between 0 and 1.")
        return value

    @field_validator("header_thresholds", mode="before")
    def str_keys_to_int(cls, v: dict[str, float]) -> dict[int, float]:
        result: dict[int, float] = {}
        for k, val in v.items():
            key_str = str(k).lower()
            if key_str.startswith("h") and key_str[1:].isdigit():
                result[int(key_str[1:])] = float(val)
            else:
                raise ValueError(f"Invalid header key: {k}")
        return result


def load_config() -> Config:
    import tomli

    with open(CONFIG_FILE_PATH, "rb") as f:
        data = tomli.load(f)

    config_data = {k.lower(): v for k, v in data.items()}
    return Config(**config_data)


config = load_config()


def set_config(new_config: Config) -> None:
    global config
    config = new_config


__all__ = ["config", "set_config"]  # allow users to set a new config if needed

if __name__ == "__main__":
    print(config)
