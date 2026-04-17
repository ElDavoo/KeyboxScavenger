from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_BANNED_SERIALS_URL = "https://raw.githubusercontent.com/daboynb/autojson/refs/heads/main/banned.txt"
DEFAULT_REVOCATION_URL = "https://android.googleapis.com/attestation/status"


class ScavengerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_id: int = Field(..., validation_alias="SCAVENGER_API_ID")
    api_hash: str = Field(..., validation_alias="SCAVENGER_API_HASH")
    session_string: str | None = Field(None, validation_alias="SCAVENGER_SESSION_STRING")
    session_name: str = Field("scavenger", validation_alias="SCAVENGER_SESSION_NAME")
    monitored_targets: list[int | str] = Field(..., validation_alias="SCAVENGER_TARGETS")

    output_dir: Path = Field(Path("data/keyboxes"), validation_alias="SCAVENGER_OUTPUT_DIR")
    max_xml_size: int = Field(20 * 1024, validation_alias="SCAVENGER_MAX_XML_SIZE")

    banned_serials_url: str = Field(
        DEFAULT_BANNED_SERIALS_URL,
        validation_alias="SCAVENGER_BANNED_SERIALS_URL",
    )
    revocation_url: str = Field(
        DEFAULT_REVOCATION_URL,
        validation_alias="SCAVENGER_REVOCATION_URL",
    )
    revocation_fallback_path: Path = Field(
        Path("res/json/status.json"),
        validation_alias="SCAVENGER_REVOCATION_FALLBACK_PATH",
    )
    leaked_serials_path: Path = Field(
        Path("leaks.txt"),
        validation_alias="SCAVENGER_LEAKED_SERIALS_PATH",
    )

    request_timeout_seconds: float = Field(
        15.0,
        validation_alias="SCAVENGER_REQUEST_TIMEOUT_SECONDS",
    )
    network_retries: int = Field(2, validation_alias="SCAVENGER_NETWORK_RETRIES")
    cache_ttl_seconds: int = Field(300, validation_alias="SCAVENGER_CACHE_TTL_SECONDS")
    log_level: str = Field("INFO", validation_alias="SCAVENGER_LOG_LEVEL")

    @field_validator("monitored_targets", mode="before")
    @classmethod
    def parse_targets(cls, value: object) -> list[int | str]:
        if isinstance(value, str):
            parsed: list[int | str] = []
            for chunk in value.split(","):
                token = chunk.strip()
                if not token:
                    continue
                token = token[1:] if token.startswith("@") else token
                if token.lstrip("-").isdigit():
                    parsed.append(int(token))
                else:
                    parsed.append(token)
            if not parsed:
                raise ValueError("SCAVENGER_TARGETS must contain at least one target")
            return parsed

        if isinstance(value, list):
            parsed = []
            for item in value:
                if isinstance(item, int):
                    parsed.append(item)
                    continue
                if isinstance(item, str):
                    token = item.strip()
                    if not token:
                        continue
                    token = token[1:] if token.startswith("@") else token
                    if token.lstrip("-").isdigit():
                        parsed.append(int(token))
                    else:
                        parsed.append(token)
            if not parsed:
                raise ValueError("SCAVENGER_TARGETS must contain at least one target")
            return parsed

        raise TypeError("SCAVENGER_TARGETS must be a CSV string or list")

    @field_validator("max_xml_size")
    @classmethod
    def validate_max_xml_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("SCAVENGER_MAX_XML_SIZE must be > 0")
        return value

    @field_validator("request_timeout_seconds")
    @classmethod
    def validate_request_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("SCAVENGER_REQUEST_TIMEOUT_SECONDS must be > 0")
        return value

    @field_validator("network_retries")
    @classmethod
    def validate_network_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("SCAVENGER_NETWORK_RETRIES must be >= 0")
        return value


def load_settings() -> ScavengerSettings:
    return ScavengerSettings()
