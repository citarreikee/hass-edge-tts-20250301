"""Support for Edge TTS."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

import edge_tts

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.components import tts as tts_component
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EdgeTtsConfigEntry, EdgeTtsData
from .const import (
    ATTR_PITCH,
    ATTR_RATE,
    ATTR_VOLUME,
    CONF_PITCH,
    CONF_RATE,
    CONF_OUTPUT_FORMAT,
    CONF_VOICE,
    CONF_VOLUME,
    DEFAULT_PITCH,
    DEFAULT_RATE,
    DEFAULT_OUTPUT_FORMAT,
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

    _attr_supported_options = [
        ATTR_VOICE,
        ATTR_RATE,
        ATTR_VOLUME,
        ATTR_PITCH,
        CONF_OUTPUT_FORMAT,
        ATTR_PREFERRED_FORMAT,
    ]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: EdgeTtsConfigEntry, voices: list[dict[str, Any]]) -> None:
        """Initialize Edge TTS entity."""
        self._entry = entry
        self._voices = voices

        self._default_voice = self._entry_value(CONF_VOICE, DEFAULT_VOICE)
        self._default_rate = self._entry_value(CONF_RATE, DEFAULT_RATE)
        self._default_volume = self._entry_value(CONF_VOLUME, DEFAULT_VOLUME)
        self._default_pitch = self._entry_value(CONF_PITCH, DEFAULT_PITCH)
        self._default_output_format = self._entry_value(
            CONF_OUTPUT_FORMAT, DEFAULT_OUTPUT_FORMAT
        )

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
            CONF_OUTPUT_FORMAT: self._default_output_format,
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
        output_format = options.get(CONF_OUTPUT_FORMAT, self._default_output_format)
        output_format = options.get(ATTR_PREFERRED_FORMAT, output_format)

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

            audio_bytes = b"".join(audio_chunks)
            audio_bytes = _strip_id3v2(audio_bytes)
            if output_format == "wav":
                try:
                    audio_bytes = await tts_component.async_convert_audio(
                        self.hass, "mp3", audio_bytes, "wav"
                    )
                    return "wav", audio_bytes
                except FileNotFoundError as err:
                    _LOGGER.warning(
                        "ffmpeg not found; falling back to mp3 output"
                    )
                except Exception as err:  # noqa: BLE001 - fallback to mp3
                    _LOGGER.warning(
                        "Failed to convert mp3->wav (%s); falling back to mp3", err
                    )
            return "mp3", audio_bytes
        except Exception as err:  # noqa: BLE001 - surface the error to the user
            _LOGGER.warning("Edge TTS request failed: %s", err, exc_info=True)
            raise HomeAssistantError("Edge TTS request failed") from err

    async def async_speak(
        self,
        media_player_entity_id: list[str],
        message: str,
        cache: bool,
        language: str | None = None,
        options: dict | None = None,
    ) -> None:
        """Speak via a Media Player.

        Use a local file path for Apple TV to avoid HTTP fetch issues.
        """
        apple_tv_ids, other_ids = self._split_media_players(media_player_entity_id)

        if other_ids:
            await super().async_speak(other_ids, message, cache, language, options)

        if not apple_tv_ids:
            return

        manager = self.hass.data[tts_component.DATA_TTS_MANAGER]
        language, merged_options = manager.process_options(self, language, options)
        extension, audio_bytes = await self.async_get_tts_audio(
            message, language, merged_options
        )

        if not extension or not audio_bytes:
            raise HomeAssistantError("No audio received from Edge TTS")

        file_path = self._write_temp_audio(audio_bytes, extension)
        await self.hass.services.async_call(
            DOMAIN_MP,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: apple_tv_ids,
                ATTR_MEDIA_CONTENT_ID: file_path,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_ANNOUNCE: True,
            },
            blocking=True,
            context=self._context,
        )
        self._schedule_temp_cleanup(file_path)

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

    def _split_media_players(self, entity_ids: list[str]) -> tuple[list[str], list[str]]:
        """Split media players into Apple TV and others."""
        if not entity_ids:
            return [], []

        registry = er.async_get(self.hass)
        apple_tv_ids: list[str] = []
        other_ids: list[str] = []

        for entity_id in entity_ids:
            entry = registry.async_get(entity_id)
            if entry and entry.platform == "apple_tv":
                apple_tv_ids.append(entity_id)
            else:
                other_ids.append(entity_id)

        return apple_tv_ids, other_ids

    def _write_temp_audio(self, audio_bytes: bytes, extension: str) -> str:
        """Write audio to a temporary file and return the path."""
        tmp = tempfile.NamedTemporaryFile(
            mode="wb", suffix=f".{extension}", delete=False
        )
        with tmp:
            tmp.write(audio_bytes)
        return tmp.name

    def _schedule_temp_cleanup(self, path: str, delay: int = 600) -> None:
        """Schedule deletion of a temporary audio file."""

        async def _cleanup(_: Any) -> None:
            try:
                os.remove(path)
            except OSError as err:
                _LOGGER.debug("Failed to remove temp TTS file %s: %s", path, err)

        async_call_later(self.hass, delay, _cleanup)


def _strip_id3v2(data: bytes) -> bytes:
    """Remove ID3v2 tag from MP3 bytes if present."""
    if len(data) < 10 or not data.startswith(b"ID3"):
        return data

    # ID3v2 header: "ID3" + ver(2) + flags(1) + size(4, synchsafe)
    size_bytes = data[6:10]
    size = 0
    for b in size_bytes:
        size = (size << 7) | (b & 0x7F)

    total = 10 + size
    if total >= len(data):
        return data
    _LOGGER.debug("Stripping ID3v2 tag of %s bytes", size)
    return data[total:]
