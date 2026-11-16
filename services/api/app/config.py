from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsConfigurationError(RuntimeError):
    """Raised when live or production settings are incomplete or still use public placeholders."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_data_dir() -> Path:
    return _repo_root() / "data"


def _is_operator_value(value: str) -> bool:
    normalized = value.strip().casefold()
    return bool(
        normalized
        and "your-" not in normalized
        and "${" not in normalized
        and not normalized.startswith("<")
        and ".example.invalid" not in normalized
        and normalized != "00000000-0000-0000-0000-000000000000"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    USE_LIVE_FOUNDRY: bool = False
    USE_LIVE_FABRIC: bool = False
    USE_LIVE_FUNDING_LLM: bool = False
    FABRIC_SQL_SERVER: str = ""
    FABRIC_SQL_DATABASE: str = ""
    USE_LIVE_WORK: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"
    DATA_DIR: Path = Field(default_factory=_default_data_dir)

    FOUNDRY_ENDPOINT: str = ""
    SEARCH_ENDPOINT: str = ""
    FOUNDRY_KB_NAME: str = ""
    FOUNDRY_KS_NAME: str = ""
    SEARCH_API_VERSION: str = "2026-05-01-preview"
    FABRIC_WORKSPACE_ID: str = ""
    FABRIC_LAKEHOUSE_ID: str = ""
    # ARM coordinates for the backing Fabric F64 capacity, used to surface its running/paused state
    # (read-only) in the UI. Read via DefaultAzureCredential against the ARM management endpoint.
    AZURE_SUBSCRIPTION_ID: str = ""
    FABRIC_CAPACITY_RG: str = ""
    FABRIC_CAPACITY_NAME: str = ""
    FABRIC_ARM_API_VERSION: str = "2023-11-01"
    ARM_SCOPE: str = "https://management.azure.com/.default"
    ARM_ENDPOINT: str = "https://management.azure.com"
    AZURE_TENANT_ID: str = ""
    API_AUDIENCE: str = ""
    API_REQUIRED_SCOPE: str = "access_as_user"
    AUTH_HTTP_TIMEOUT_SECONDS: float = 10.0
    APP_ENVIRONMENT: str = "production"
    AZURE_CLIENT_ID: str = ""
    WORK_IQ_ENDPOINT: str = "https://workiq.svc.cloud.microsoft/a2a/"
    WORK_IQ_MCP_ENDPOINT: str = "https://workiq.svc.cloud.microsoft/mcp"
    WORK_IQ_SCOPE: str = "api://workiq.svc.cloud.microsoft/.default"
    WORK_IQ_CLIENT_ID: str = ""
    WORK_IQ_FUNDING_DOCUMENT_URLS: str = ""
    WORK_IQ_FUNDING_DOCUMENT_IDENTITIES: str = ""
    WORK_IQ_KEY_VAULT_URL: str = ""
    WORK_IQ_CLIENT_CERTIFICATE_SECRET_NAME: str = ""
    WORK_IQ_CLIENT_CERTIFICATE: str = ""
    WORK_IQ_CLIENT_CERTIFICATE_THUMBPRINT: str = ""
    WORK_IQ_CLIENT_PUBLIC_CERTIFICATE: str = ""
    WORK_IQ_CERTIFICATE_CACHE_SECONDS: float = 300.0
    WORK_IQ_CERTIFICATE_REFRESH_RETRY_SECONDS: float = 30.0
    WORK_IQ_TIMEOUT_SECONDS: float = 60.0
    WORK_IQ_TIMEZONE: str = "America/Chicago"
    WORK_IQ_TIMEZONE_OFFSET_MINUTES: int = -300
    MODEL_DEPLOYMENT: str = ""

    @property
    def live_components_enabled(self) -> bool:
        return any(
            (
                self.USE_LIVE_FOUNDRY,
                self.USE_LIVE_FUNDING_LLM,
                self.USE_LIVE_FABRIC,
                self.USE_LIVE_WORK,
            )
        )

    @property
    def anonymous_mock_enabled(self) -> bool:
        """Allow anonymous deterministic requests only in an explicitly local/test environment."""
        local_environment = self.APP_ENVIRONMENT.strip().casefold() in {
            "development",
            "dev",
            "local",
            "test",
        }
        return local_environment and not self.live_components_enabled

    @computed_field
    @property
    def mode(self) -> Literal["mock", "live"]:
        return "mock" if self.anonymous_mock_enabled else "live"

    def validate_runtime_configuration(self) -> None:
        """Fail before startup when a live/production process lacks explicit operator settings."""
        if self.anonymous_mock_enabled:
            return

        required = {
            "AZURE_TENANT_ID",
            "API_AUDIENCE",
            "API_REQUIRED_SCOPE",
        }
        if self.USE_LIVE_FUNDING_LLM and not self.USE_LIVE_FOUNDRY:
            raise SettingsConfigurationError("Live funding synthesis requires USE_LIVE_FOUNDRY=true.")
        if not self.USE_LIVE_FABRIC:
            raise SettingsConfigurationError("Connected funding deployments require USE_LIVE_FABRIC=true.")
        required.update({
            "FABRIC_WORKSPACE_ID", "FABRIC_LAKEHOUSE_ID",
            "FABRIC_SQL_SERVER", "FABRIC_SQL_DATABASE", "AZURE_CLIENT_ID",
        })
        if self.USE_LIVE_FOUNDRY:
            required.update({"SEARCH_ENDPOINT", "FOUNDRY_KB_NAME"})
            required.add("FOUNDRY_KS_NAME")
        if self.USE_LIVE_FUNDING_LLM:
            required.update({"FOUNDRY_ENDPOINT", "MODEL_DEPLOYMENT"})
        if self.USE_LIVE_WORK:
            required.update(
                {
                    "WORK_IQ_CLIENT_ID",
                    "WORK_IQ_ENDPOINT",
                    "WORK_IQ_SCOPE",
                }
            )
            required.add("WORK_IQ_FUNDING_DOCUMENT_URLS")
            if self.APP_ENVIRONMENT.strip().casefold() == "production":
                required.update(
                    {
                        "AZURE_CLIENT_ID",
                        "WORK_IQ_KEY_VAULT_URL",
                        "WORK_IQ_CLIENT_CERTIFICATE_SECRET_NAME",
                    }
                )
            else:
                required.update(
                    {
                        "WORK_IQ_CLIENT_CERTIFICATE",
                        "WORK_IQ_CLIENT_CERTIFICATE_THUMBPRINT",
                    }
                )

        missing = sorted(
            name for name in required if not _is_operator_value(str(getattr(self, name)))
        )
        if missing:
            raise SettingsConfigurationError(
                "Live/production configuration is incomplete or still uses public placeholders: "
                + ", ".join(missing)
            )

    @property
    def fabric_portal_url(self) -> str:
        if not self.FABRIC_WORKSPACE_ID.strip():
            return ""
        return f"https://app.fabric.microsoft.com/groups/{self.FABRIC_WORKSPACE_ID}"

    @property
    def fabric_capacity_resource_id(self) -> str:
        return (
            f"/subscriptions/{self.AZURE_SUBSCRIPTION_ID}"
            f"/resourceGroups/{self.FABRIC_CAPACITY_RG}"
            f"/providers/Microsoft.Fabric/capacities/{self.FABRIC_CAPACITY_NAME}"
        )

    @property
    def fabric_capacity_arm_url(self) -> str:
        return f"{self.ARM_ENDPOINT}{self.fabric_capacity_resource_id}?api-version={self.FABRIC_ARM_API_VERSION}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def token_issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}/v2.0"

    @property
    def jwks_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}/discovery/v2.0/keys"

    @property
    def obo_authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime_configuration()
    return settings
