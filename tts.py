"""Support for Edge TTS."""

from __future__ import annotations

import logging
from typing import Any

import edge_tts

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EdgeTtsConfigEntry, EdgeTtsData
from .const import (
    ATTR_PITCH,
    ATTR_RATE,
    ATTR_VOLUME,
    CONF_PITCH,
    CONF_RATE,
    CONF_VOICE,
    CONF_VOLUME,
    DEFAULT_PITCH,
    DEFAULT_RATE,
    DEFAULT_VOICE,
    DEFAULT_VOLUME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _locale_from_voice(voice: str) -> str:
    """Extract locale from voice short name."""
    parts = voice.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return "en-US"


async def _async_fetch_voices() -> list[dict[str, Any]]:
    """Fetch available voices from Edge TTS."""
    try:
        return await edge_tts.list_voices()
    except Exception as err:  # noqa: BLE001 - network and API errors are expected
        _LOGGER.warning("Failed to fetch Edge TTS voices: %s", err)
        return []


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EdgeTtsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Edge TTS platform via config entry."""
    voices = await _async_fetch_voices()
    config_entry.runtime_data = EdgeTtsData(voices=voices)

    async_add_entities([EdgeTTSEntity(config_entry, voices)])


class EdgeTTSEntity(TextToSpeechEntity):
    """Edge TTS entity."""

    _attr_supported_options = [ATTR_VOICE, ATTR_RATE, ATTR_VOLUME, ATTR_PITCH]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: EdgeTtsConfigEntry, voices: list[dict[str, Any]]) -> None:
        """Initialize Edge TTS entity."""
        self._entry = entry
        self._voices = voices

        self._default_voice = self._entry_value(CONF_VOICE, DEFAULT_VOICE)
        self._default_rate = self._entry_value(CONF_RATE, DEFAULT_RATE)
        self._default_volume = self._entry_value(CONF_VOLUME, DEFAULT_VOLUME)
        self._default_pitch = self._entry_value(CONF_PITCH, DEFAULT_PITCH)

        locales = sorted({v.get("Locale") for v in voices if v.get("Locale")})
        default_locale = _locale_from_voice(self._default_voice)
        if default_locale not in locales:
            locales.append(default_locale)
        self._attr_supported_languages = locales
        self._attr_default_language = default_locale

        self._attr_default_options = {
            ATTR_VOICE: self._default_voice,
            ATTR_RATE: self._default_rate,
            ATTR_VOLUME: self._default_volume,
            ATTR_PITCH: self._default_pitch,
        }

        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Microsoft",
            model="Edge TTS",
        )

    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return list of supported voices for a language."""
        if not self._voices:
            return None

        language = language.lower()
        voices = [
            voice
            for voice in self._voices
            if voice.get("Locale", "").lower().startswith(language)
            or voice.get("Locale", "").split("-")[0].lower() == language
        ]
        return [
            Voice(
                voice_id=voice["ShortName"],
                name=voice.get("FriendlyName") or voice.get("Name") or voice["ShortName"],
            )
            for voice in voices
        ]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        options = options or {}

        voice = options.get(ATTR_VOICE) or self._default_voice
        if language and ATTR_VOICE not in options:
            voice = self._voice_for_language(language) or voice

        rate = options.get(ATTR_RATE, self._default_rate)
        volume = options.get(ATTR_VOLUME, self._default_volume)
        pitch = options.get(ATTR_PITCH, self._default_pitch)

        try:
            communicate = edge_tts.Communicate(
                message,
                voice,
                rate=str(rate),
                volume=str(volume),
                pitch=str(pitch),
            )
            audio_chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])

            if not audio_chunks:
                raise HomeAssistantError("No audio received from Edge TTS")

            return "mp3", b"".join(audio_chunks)
        except Exception as err:  # noqa: BLE001 - surface the error to the user
            _LOGGER.warning("Edge TTS request failed: %s", err, exc_info=True)
            raise HomeAssistantError("Edge TTS request failed") from err

    def _voice_for_language(self, language: str) -> str | None:
        """Pick the first voice matching the requested language."""
        if not self._voices:
            return None

        language = language.lower()
        for voice in self._voices:
            locale = voice.get("Locale", "").lower()
            if locale.startswith(language) or locale.split("-")[0] == language:
                return voice.get("ShortName")
        return None

    def _entry_value(self, key: str, default: str) -> str:
        """Return option value, falling back to entry data and defaults."""
        if key in self._entry.options:
            return str(self._entry.options[key])
        if key in self._entry.data:
            return str(self._entry.data[key])
        return default
