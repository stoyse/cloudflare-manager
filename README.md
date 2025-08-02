# Cloudflare Tunnel Manager

A modern, interactive shell app for managing multiple Cloudflare tunnels on your server. Features a beautiful terminal UI, arrow-key navigation, and full tunnel lifecycle management.

## Features

- List all existing Cloudflare tunnels
- Create new tunnels with custom DNS and local service mapping
- Each tunnel has its own config and startup script
- Systemd integration: tunnels run as services and restart on boot
- Delete tunnels (removes service, config, and Cloudflare tunnel)
- Display tunnel info: view config, activate/deactivate service
- Settings menu:
  - Change where tunnel configs are saved
  - Log in to Cloudflare (`cloudflared login`)
- All navigation is via arrow keys (no typing numbers!)

## Requirements

- Python 3.8+
- `cloudflared` installed and in your PATH ([Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/))
- Linux system with `systemd` (for service management)

## Installation

1. **Clone this repo**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **(Optional) Compile to a single binary:**
   ```bash
   pip install pyinstaller
   pyinstaller --onefile --name tunnel_manager tunnel_manager.py
   # The binary will be in the dist/ folder
   ```

## Usage

Run the app:
```bash
python tunnel_manager.py
```
Or, if compiled:
```bash
./dist/tunnel_manager
```

### Main Menu
- Use the arrow keys to navigate.
- Press Enter to select an option.

### Settings
- Change the directory where tunnel configs are stored (persisted in `settings.json`).
- Log in to Cloudflare (opens browser for authentication).

### Creating a Tunnel
- Enter a tunnel name, DNS name, and local service URL.
- The app creates the tunnel, config, startup script, and systemd service.

### Managing Tunnels
- View config, activate/deactivate the systemd service, or delete the tunnel.

## Notes
- You may need `sudo` for some operations (systemd service management).
- All tunnel configs and scripts are stored in the directory you choose in Settings.
- The app is safe to use repeatedly and will not overwrite existing tunnels.

## License
MIT
