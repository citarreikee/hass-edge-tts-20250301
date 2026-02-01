"""The Edge TTS integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.TTS]


@dataclass(kw_only=True, slots=True)
class EdgeTtsData:
    """Runtime data for Edge TTS."""

    voices: list[dict]


type EdgeTtsConfigEntry = ConfigEntry[EdgeTtsData]


async def async_setup_entry(hass: HomeAssistant, entry: EdgeTtsConfigEntry) -> bool:
    """Set up Edge TTS from a config entry."""
    if "output_format" in entry.options:
        options = dict(entry.options)
        options.pop("output_format", None)
        hass.config_entries.async_update_entry(entry, options=options)
    entry.add_update_listener(update_listener)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EdgeTtsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: EdgeTtsConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
