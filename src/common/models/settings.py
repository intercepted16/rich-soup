"""Settings models for Rich Soup."""

from pydantic import BaseModel


class Settings(BaseModel):
    """Settings for Rich Soup."""

    reading_order: str = "ltr"  # left-to-right or right-to-left
    extract_images: bool = False
    timeout: int = 30  # seconds
    user_agent: str | None = None  # custom user agent string
