# Edge TTS for Home Assistant

Use the Microsoft Edge TTS service through the `edge-tts` Python library.
This custom integration implements Home Assistant's modern TTS entity API
and avoids the legacy `async_create_stream` helper.

## Features
- Configurable default voice, rate, volume, and pitch.
- Supports `tts.speak` and TTS media source playback.
- Auto-detects supported languages from the Edge voice catalog when available.

## Requirements
- Home Assistant core (recent versions that include the `TextToSpeechEntity` API).
- `edge-tts` Python package (installed automatically by HA via `manifest.json`).

## Installation (manual)
1. Copy the `edge_tts` folder into `config/custom_components/`.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and search for **Edge TTS**.

## Configuration
The UI flow asks for:
- **Voice**: Example `en-US-EmmaMultilingualNeural`, `zh-CN-XiaoxiaoNeural`
- **Rate**: Example `+0%`, `-10%`
- **Volume**: Example `+0%`, `-10%`
- **Pitch**: Example `+0Hz`, `-50Hz`

You can adjust these later in **Options**.

## Example service call
```yaml
action: tts.speak
data:
  media_player_entity_id: media_player.your_speaker
  message: "Hello from Edge TTS"
  options:
    voice: "en-US-EmmaMultilingualNeural"
    rate: "+0%"
    volume: "+0%"
    pitch: "+0Hz"
```

## Troubleshooting
- **403 / Invalid response status**: This is usually a temporary service-side
  issue or a clock-skew/DNS problem. The underlying `edge-tts` library already
  handles some skew cases, but you may still need to retry.
- **No audio received**: Check network/DNS connectivity from the Home Assistant
  host to `speech.platform.bing.com`.

## Notes
- Voice listing is fetched at startup. If it fails (DNS, network), the integration
  still works with the configured default voice.

## License
MIT
