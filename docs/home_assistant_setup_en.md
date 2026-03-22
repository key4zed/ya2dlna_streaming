# Integration with Home Assistant

This guide describes how to connect the ya2dlna_streaming application to Home Assistant for managing audio streaming from a Yandex Station to a DLNA device.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installing the ya2dlna_streaming application](#installing-the-ya2dlna_streaming-application)
3. [Setting up Yandex Music token](#setting-up-yandex-music-token)
4. [Starting the server](#starting-the-server)
5. [Verifying API operation](#verifying-api-operation)
6. [Method 1: RESTful Command + Template Switch (simple)](#method-1-restful-command--template-switch-simple)
7. [Method 2: Custom component (advanced)](#method-2-custom-component-advanced)
8. [Method 3: Installation via HACS](#method-3-installation-via-hacs)
9. [Method 4: Home Assistant add‑on (recommended)](#method-4-home-assistant-add‑on-recommended)
10. [Automation](#automation)
11. [Troubleshooting](#troubleshooting)
12. [Notes](#notes)

## Prerequisites

- Home Assistant version 2023.x or higher.
- Access to Home Assistant configuration (`configuration.yaml`).
- Network where Yandex Station and DLNA device are reachable.
- Yandex Music token (for accessing audio streams).

## Installing the ya2dlna_streaming application

### Option A: Install from source

```bash
git clone https://github.com/your-repo/ya2dlna_streaming.git
cd ya2dlna_streaming
pip install -r requirements.txt
```

### Option B: Install via Docker

```bash
docker build -t ya2dlna_streaming .
docker run -d --name ya2dlna -p 8000:8000 ya2dlna_streaming
```

## Setting up Yandex Music token

1. Obtain a Yandex Music token (instructions: [How to get a token](https://github.com/MarshalX/yandex-music-api/discussions/513)).
2. Create a `.env` file in the project root or set the environment variable:
   ```bash
   export YANDEX_MUSIC_TOKEN=your_token_here
   ```
3. For Docker, add the variable to `docker run`:
   ```bash
   docker run -d -e YANDEX_MUSIC_TOKEN=your_token_here -p 8000:8000 ya2dlna_streaming
   ```

## Starting the server

### Manually

```bash
python -m src.api.main
```

The server will start at `http://0.0.0.0:8000`.

### Via Docker Compose

Copy `docker-compose.yml` and run:

```bash
docker-compose up -d
```

## Verifying API operation

Ensure the API server is running and accessible:

```bash
curl http://localhost:8000/ha/devices
```

Should return a JSON list of devices.

Home Assistant endpoints:

- `GET /ha/devices` – list of devices
- `POST /ha/source/{id}` – select source
- `POST /ha/target/{id}` – select target
- `POST /ha/stream/start` – start streaming
- `POST /ha/stream/stop` – stop streaming

## Method 1: RESTful Command + Template Switch (simple)

Add the following sections to `configuration.yaml`:

```yaml
rest_command:
  ya2dlna_set_source:
    url: "http://<IP>:8000/ha/source/{{ device_id }}"
    method: POST
  ya2dlna_set_target:
    url: "http://<IP>:8000/ha/target/{{ device_id }}"
    method: POST
  ya2dlna_start_stream:
    url: "http://<IP>:8000/ha/stream/start"
    method: POST
  ya2dlna_stop_stream:
    url: "http://<IP>:8000/ha/stream/stop"
    method: POST

sensor:
  - platform: rest
    name: "Ya2DLNA Devices"
    resource: "http://<IP>:8000/ha/devices"
    scan_interval: 60
    value_template: "{{ value_json | length }}"
    json_attributes:
      - device_id
      - name
      - device_type

switch:
  - platform: template
    switches:
      ya2dlna_streaming:
        friendly_name: "Ya2DLNA Streaming"
        value_template: "{{ is_state('sensor.ya2dlna_stream_status', 'streaming') }}"
        turn_on:
          service: rest_command.ya2dlna_start_stream
        turn_off:
          service: rest_command.ya2dlna_stop_stream
```

Replace `<IP>` with the IP address of the host where the server is running.

## Method 2: Custom component (advanced)

### Step 1: Copy the component

Create a directory `custom_components/ya2dlna/` in your Home Assistant configuration folder (usually `~/.homeassistant/` or `/config/`).

Copy all files from the `custom_components/ya2dlna/` folder of this repository:

- `manifest.json`
- `const.py`
- `__init__.py`
- `config_flow.py`
- `switch.py`

### Step 2: Restart Home Assistant

Restart Home Assistant (via UI: **Settings → System → Restart**).

### Step 3: Add the integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for "Ya2DLNA Streaming" and click it.
3. Enter the server IP and port (default `localhost:8000` if the server runs on the same host).
4. Click "Submit".

### Step 4: Select devices

After connecting to the server, you will be prompted to select entities:

1. **Yandex Station (source)** – select the media_player entity corresponding to your Yandex Station.
2. **DLNA device (target)** – select the media_player entity corresponding to the DLNA renderer.

Click "Finish".

### Step 5: Using the switch

A new switch "Ya2DLNA Streaming" will appear in your devices. Turning it on starts streaming, turning it off stops streaming.

## Method 3: Installation via HACS

[HACS](https://hacs.xyz/) (Home Assistant Community Store) is a custom component store for Home Assistant. The ya2dlna_streaming integration is available for installation via HACS.

### Prerequisites

- HACS installed (installation guide: [https://hacs.xyz/docs/setup/download](https://hacs.xyz/docs/setup/download)).

### Adding the repository

1. Open HACS in the Home Assistant interface.
2. Go to the **Integrations** section.
3. Click the three dots in the upper right corner and select **Custom repositories**.
4. In the "Repository" field, enter the URL of this repository: `https://github.com/your-repo/ya2dlna_streaming`.
5. From the dropdown, select **Integration**.
6. Click **Add**.

### Installing the integration

1. After adding the repository, **Ya2DLNA Streaming** will appear in the list of integrations in HACS.
2. Click on it, then click **Install**.
3. Wait for the installation to complete.
4. Restart Home Assistant.

### Configuration

After restarting, add the integration via UI (Settings → Devices & Services → Add Integration → Ya2DLNA Streaming) and follow steps 3–5 from Method 2.

## Method 4: Home Assistant add‑on (recommended)

The add‑on automatically deploys the ya2dlna_streaming server inside Home Assistant, eliminating the need to run the application manually.

### Installing the add‑on

#### For Hass.io / Home Assistant OS

1. Add the add‑on repository to Home Assistant:
   - Go to **Supervisor → Add‑on Store → Add repository**.
   - Enter the repository URL: `https://github.com/your-repo/ya2dlna_streaming`.
   - Click **Add**.
2. After the repository appears, find the **Ya2DLNA Streaming** add‑on and click **Install**.
3. Configure the add‑on parameters:
   - **YANDEX_MUSIC_TOKEN**: your Yandex Music token.
   - **PORT**: server port (default 8000).
   - **LOG_LEVEL**: logging level.
4. Start the add‑on.

#### For Home Assistant Container

Add‑ons are not supported. Use Method 1, 2 or 3.

### Usage

Once the add‑on is running, the server will be available inside the Home Assistant network at `http://ya2dlna:8000`. The custom component integration (Method 2 or 3) will automatically discover this server if you specify host `ya2dlna` and port `8000` in the configuration.

## Automation

Example automation to start streaming when Yandex Station starts playing:

```yaml
automation:
  - alias: "Start streaming when Yandex Station plays"
    trigger:
      platform: state
      entity_id: media_player.yandex_station
      to: "playing"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.ya2dlna_streaming
```

Example automation to stop streaming when Yandex Station is paused:

```yaml
automation:
  - alias: "Stop streaming when Yandex Station paused"
    trigger:
      platform: state
      entity_id: media_player.yandex_station
      to: "paused"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.ya2dlna_streaming
```

## Troubleshooting

### Server does not start

- Check if the Yandex Music token is set.
- Ensure port 8000 is not occupied.
- Check logs: `docker logs <container_name>` or application logs.

### Devices not discovered

- Make sure Yandex Station and DLNA device are on the same network.
- Verify that mDNS (Bonjour) is working on the network.
- Enable UPnP on the DLNA device.

### Integration fails to connect

- Verify the server is reachable from Home Assistant: `curl http://<IP>:8000/ha/devices`.
- Ensure the correct IP and port are specified in the integration settings.

### Streaming does not work

- Check that Yandex Station is playing music.
- Ensure the DLNA device is powered on and reachable.
- Check server logs for errors.

## Notes

- The ya2dlna_streaming application must be running on the same host or accessible over the network.
- Make sure the correct hosts and ports are set in the application settings (`settings.py`).
- This integration is under development, changes are possible.
- Source code and updates: [GitHub repository](https://github.com/your-repo/ya2dlna_streaming).