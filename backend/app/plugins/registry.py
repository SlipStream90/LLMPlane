"""Plugin discovery & registration (R2).

Scans plugins/providers/<name>/manifest.json at startup, imports the module
each manifest points to, and instantiates the ProviderPlugin subclass it
exports as PLUGIN. A broken plugin (missing file, bad JSON, import error,
manifest that fails validation) is logged and skipped — never a boot
failure. This mirrors GatewayClient.CompletionResult's "failure is a value"
pattern (Article XIV): one bad third-party plugin must not take the app down.

Directory-convention scan, not `pyproject.toml` entry_points: plugins live
in-monorepo under `app/plugins/providers/`, not distributed as separate
installable packages, so `entry_points` buys nothing here.
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path

from app.plugins.base import ProviderManifest, ProviderPlugin
from app.services.gateway_client import GatewayClient

logger = logging.getLogger(__name__)

_PROVIDERS_DIR = Path(__file__).parent / "providers"
_REQUIRED_MANIFEST_KEYS = {
    "id",
    "display_name",
    "auth_type",
    "default_base_url",
    "requires_base_url",
    "capabilities",
    "module",
}
_VALID_AUTH_TYPES = {"api_key", "none", "bearer_token"}


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, ProviderPlugin] = {}

    def get(self, plugin_id: str) -> ProviderPlugin | None:
        return self._plugins.get(plugin_id)

    def list_manifests(self) -> list[ProviderManifest]:
        return [p.manifest for p in self._plugins.values()]

    async def discover(self, gateway: GatewayClient) -> None:
        """Scan plugins/providers/*, load + validate + instantiate each.
        Called once from app.main's lifespan, before the app starts serving.
        """
        if not _PROVIDERS_DIR.is_dir():
            logger.warning("Plugin providers directory not found: %s", _PROVIDERS_DIR)
            return

        for entry in sorted(_PROVIDERS_DIR.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.is_file():
                logger.warning("Skipping plugin dir '%s': no manifest.json", entry.name)
                continue
            try:
                raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._validate_manifest(raw, dir_name=entry.name)
                manifest = ProviderManifest(
                    id=raw["id"],
                    display_name=raw["display_name"],
                    auth_type=raw["auth_type"],
                    default_base_url=raw.get("default_base_url"),
                    requires_base_url=bool(raw["requires_base_url"]),
                    capabilities=list(raw["capabilities"]),
                    pricing_hint=raw.get("pricing_hint"),
                )
                module = importlib.import_module(raw["module"])
                plugin_cls = module.PLUGIN
                plugin: ProviderPlugin = plugin_cls(gateway)
                plugin.manifest = manifest
                await plugin.initialize()
                self._plugins[manifest.id] = plugin
                logger.info("Registered provider plugin '%s'", manifest.id)
            except Exception:
                # Broad except deliberately: any single plugin's failure mode
                # (bad JSON, missing module, raised exception in initialize())
                # must not abort the scan for the remaining plugins, and must
                # not abort app startup (R2 fail-open).
                logger.exception(
                    "Failed to load plugin from '%s' — skipping.", entry.name
                )

    @staticmethod
    def _validate_manifest(raw: dict, *, dir_name: str) -> None:
        missing = _REQUIRED_MANIFEST_KEYS - raw.keys()
        if missing:
            raise ValueError(f"manifest for '{dir_name}' missing keys: {missing}")
        if raw["id"] != dir_name:
            raise ValueError(
                f"manifest id '{raw['id']}' must match directory name '{dir_name}'"
            )
        if raw["auth_type"] not in _VALID_AUTH_TYPES:
            raise ValueError(f"invalid auth_type '{raw['auth_type']}' in '{dir_name}'")

    async def shutdown(self) -> None:
        for plugin in self._plugins.values():
            await plugin.shutdown()


# Process-lifetime singleton, mirroring init_engine()/init_redis() in
# core/db.py and core/redis.py — created empty at import time, populated by
# discover() during lifespan startup, read by request handlers thereafter.
_registry = PluginRegistry()


def get_plugin_registry() -> PluginRegistry:
    return _registry
