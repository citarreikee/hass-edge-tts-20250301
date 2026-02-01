"""Config flow for Edge TTS integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
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

RATE_RE = re.compile(r"^[+-]?\d+%$")
PITCH_RE = re.compile(r"^[+-]?\d+Hz$")


def _validate_options(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate options and return errors."""
    errors: dict[str, str] = {}

    rate = user_input.get(CONF_RATE, DEFAULT_RATE)
    volume = user_input.get(CONF_VOLUME, DEFAULT_VOLUME)
    pitch = user_input.get(CONF_PITCH, DEFAULT_PITCH)

    if rate and not RATE_RE.match(str(rate)):
        errors[CONF_RATE] = "invalid_rate"
    if volume and not RATE_RE.match(str(volume)):
        errors[CONF_VOLUME] = "invalid_volume"
    if pitch and not PITCH_RE.match(str(pitch)):
        errors[CONF_PITCH] = "invalid_pitch"

    return errors


USER_STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VOICE, default=DEFAULT_VOICE): str,
        vol.Required(CONF_RATE, default=DEFAULT_RATE): str,
        vol.Required(CONF_VOLUME, default=DEFAULT_VOLUME): str,
        vol.Required(CONF_PITCH, default=DEFAULT_PITCH): str,
        vol.Required(
            CONF_OUTPUT_FORMAT, default=DEFAULT_OUTPUT_FORMAT
        ): vol.In(["mp3", "wav"]),
    }
)


class EdgeTtsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Edge TTS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_options(user_input)
            if not errors:
                voice = user_input[CONF_VOICE]
                return self.async_create_entry(
                    title=f"Edge TTS ({voice})",
                    data={},
                    options=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_STEP_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Create the options flow."""
        return EdgeTtsOptionsFlow(config_entry)


class EdgeTtsOptionsFlow(OptionsFlow):
    """Handle an options flow for Edge TTS."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_options(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VOICE,
                        default=self.config_entry.options.get(
                            CONF_VOICE, DEFAULT_VOICE
                        ),
                    ): str,
                    vol.Required(
                        CONF_RATE,
                        default=self.config_entry.options.get(
                            CONF_RATE, DEFAULT_RATE
                        ),
                    ): str,
                    vol.Required(
                        CONF_VOLUME,
                        default=self.config_entry.options.get(
                            CONF_VOLUME, DEFAULT_VOLUME
                        ),
                    ): str,
                    vol.Required(
                        CONF_PITCH,
                        default=self.config_entry.options.get(
                            CONF_PITCH, DEFAULT_PITCH
                        ),
                    ): str,
                    vol.Required(
                        CONF_OUTPUT_FORMAT,
                        default=self.config_entry.options.get(
                            CONF_OUTPUT_FORMAT, DEFAULT_OUTPUT_FORMAT
                        ),
                    ): vol.In(["mp3", "wav"]),
                }
            ),
            errors=errors,
        )
