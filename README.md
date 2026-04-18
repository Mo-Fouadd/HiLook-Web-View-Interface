# HiLook Smart-View Web Interface

A Python Flask application for simultaneously monitoring and interacting with HiLook/Hikvision DVR camera feeds. It uses ISAPI for grid snapshot polling and OpenCV with FFmpeg for fullscreen RTSP streams.

## Required DVR Configuration

**1. Disable Encryption**
Image and video encryption must be disabled to allow third-party access.
* Open the Hik-Connect / HiLook phone app.
* Select the DVR.
* Tap the settings icon.
* Toggle off **Image and Video Encryption**.

**2. DVR Video & Audio Settings**
The application is tested and optimized for the following stream configuration:
* **Camera:** `[A{}] Camera 0{}`
* **Front-end Resolution:** `960*1080(1080PLite)P25`
* **Stream Type:** `Main Stream(Normal)`
* **Video Type:** `Video Stream`
* **Resolution:** `960*1080(1080P Lite)`
* **Bitrate Type:** `Variable`
* **Video Quality:** `Highest`
* **Frame Rate:** `15 fps`
* **Max. Bitrate:** `512 Kbps`
* **Video Encoding:** `H.264`
* **H.264+:** `OFF`

## Installation

1. Clone the repository.
2. Initialize a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to input your DVR IP, username, password, and active camera list.

## Usage

Start the Flask server:
```bash
python app.py
```

Access the interface at `http://<YOUR_IP>:5000`.

* **Grid View:** Displays snapshots polling at the interval defined in `.env`.
* **Fullscreen:** Double-click any camera to initiate a live RTSP stream.
* **Navigation:** Use arrow keys (`Left/Right` or `Up/Down`) to cycle through cameras while in fullscreen. Press `Escape` to return to the grid.
