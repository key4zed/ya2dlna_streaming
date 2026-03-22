# Ya2DLNA Streaming Add‑on

This add‑on runs the ya2dlna_streaming application as a service inside Home Assistant.

## Configuration

Configure the add‑on via the Home Assistant UI (Settings → Add‑ons → Ya2DLNA Streaming → Configuration). The following options are available:

- **ya_music_token** – Yandex Music API token (required).
- **ruark_pin** – PIN code for Ruark R5 (if using Ruark).
- **local_server_host** – Host address for the streaming server (default: `0.0.0.0`).
- **local_server_port_dlna** – Port for DLNA streaming server (default: `8001`).
- **local_server_port_api** – Port for REST API (default: `8000`).
- **stream_quality** – Audio quality (`192`, `320`, etc.).
- **debug** – Enable debug logging.

## Usage

After starting the add‑on, the streaming server will be available at `http://<hassio_ip>:8000`. The custom component `ya2dlna` can then communicate with this server.

## Logs

Logs are available in the add‑on log panel.

## Support

For issues, please refer to the [main project repository](https://github.com/your-repo/ya2dlna_streaming).