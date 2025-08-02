import os
import subprocess
import sys
import json
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from simple_term_menu import TerminalMenu

SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"tunnels_dir": "tunnels"}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

settings = load_settings()
TUNNELS_DIR = settings.get("tunnels_dir", "tunnels")

console = Console()


def list_tunnels():
    table = Table(title="Existing Tunnels")
    table.add_column("Tunnel Name", style="cyan", no_wrap=True)
    tunnels = [
        tunnel_name
        for tunnel_name in os.listdir(TUNNELS_DIR)
        if os.path.isdir(os.path.join(TUNNELS_DIR, tunnel_name))
    ]
    if not tunnels:
        console.print("[yellow]No tunnels found.[/yellow]")
    else:
        for tunnel_name in tunnels:
            table.add_row(tunnel_name)
        console.print(table)


def create_tunnel():
    console.clear()
    console.print(Panel("Create a New Tunnel", style="bold blue"))
    tunnel_name = Prompt.ask("Enter the tunnel name")
    dns_name = Prompt.ask("Enter the DNS name (e.g., myapp.mydomain.com)")
    service_url = Prompt.ask("Enter the local service URL (e.g., http://localhost:8000)")

    tunnel_path = os.path.join(TUNNELS_DIR, tunnel_name)
    if os.path.exists(tunnel_path):
        console.print(f"[red]Tunnel '{tunnel_name}' already exists.[/red]")
        return

    os.makedirs(tunnel_path)

    try:
        # Create the tunnel
        console.print(f"Creating Cloudflare tunnel '{tunnel_name}'...")
        create_tunnel_cmd = ["cloudflared", "tunnel", "create", tunnel_name]
        result = subprocess.run(create_tunnel_cmd, capture_output=True, text=True, check=True)
        console.print(f"[green]{result.stdout}[/green]")

        # Find the credentials file path from the output
        creds_file_path = ""
        for line in result.stdout.splitlines():
            if ".json" in line:
                # This is a simple way to find the path, might need to be more robust
                creds_file_path = line.split("to ")[1].split(". ")[0]
                break

        if not creds_file_path:
            console.print("[red]Could not find the credentials file path in the output.[/red]")
            return

        # Create config.yml
        config_path = os.path.join(tunnel_path, "config.yml")
        config_content = f"""
tunnel: {tunnel_name}
credentials-file: {creds_file_path}
ingress:
  - hostname: {dns_name}
    service: {service_url}
  - service: http_status:404
"""
        with open(config_path, "w") as f:
            f.write(config_content)
        console.print(f"Created config file at [cyan]{config_path}[/cyan]")

        # Create startup script
        script_path = os.path.join(tunnel_path, "start_tunnel.sh")
        script_content = f"""#!/bin/bash
cloudflared tunnel --config {os.path.abspath(config_path)} run
"""
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        console.print(f"Created startup script at [cyan]{script_path}[/cyan]")

        # Create and install systemd service
        service_name = f"cloudflare-tunnel-{tunnel_name}"
        service_file_path = f"/etc/systemd/system/{service_name}.service"
        service_content = f"""[Unit]
Description=Cloudflare Tunnel for {tunnel_name}
After=network.target

[Service]
ExecStart={os.path.abspath(script_path)}
Restart=always
User={os.getlogin()}

[Install]
WantedBy=multi-user.target
"""
        try:
            with open(service_file_path, "w") as f:
                f.write(service_content)
            console.print(f"Created systemd service file at [cyan]{service_file_path}[/cyan]")

            console.print("Reloading systemd daemon...")
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            console.print(f"Enabling and starting service {service_name}...")
            subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
            subprocess.run(["sudo", "systemctl", "start", service_name], check=True)
            console.print("[green]Tunnel service started and enabled.[/green]")

        except PermissionError:
            console.print("\n---")
            console.print("[yellow]Could not create or install the systemd service due to permission errors.[/yellow]")
            console.print("Please run the following commands with sudo to complete the setup:")
            console.print(f"sudo bash -c 'cat > {service_file_path}' << EOF\n{service_content}EOF")
            console.print("sudo systemctl daemon-reload")
            console.print(f"sudo systemctl enable --now {service_name}")
            console.print("---")

    except FileNotFoundError:
        console.print("[red]Error: 'cloudflared' command not found.[/red]")
        console.print("Please make sure Cloudflare Tunnel is installed and in your PATH.")
    except subprocess.CalledProcessError as e:
        console.print("[red]Error creating tunnel:[/red]")
        console.print(e.stderr)


def delete_tunnel():
    console.clear()
    console.print(Panel("Delete a Tunnel", style="bold red"))
    list_tunnels()
    tunnel_name = Prompt.ask("\nEnter the name of the tunnel to delete")

    tunnel_path = os.path.join(TUNNELS_DIR, tunnel_name)
    if not os.path.exists(tunnel_path):
        console.print(f"[red]Tunnel '{tunnel_name}' not found.[/red]")
        return

    if not Confirm.ask(f"Are you sure you want to delete the tunnel '{tunnel_name}'? This will stop the service and remove all its files."):
        console.print("[yellow]Deletion cancelled.[/yellow]")
        return

    try:
        # Stop and disable systemd service
        service_name = f"cloudflare-tunnel-{tunnel_name}"
        console.print(f"Stopping and disabling systemd service '{service_name}'...")
        subprocess.run(["sudo", "systemctl", "stop", service_name], check=False)
        subprocess.run(["sudo", "systemctl", "disable", service_name], check=False)

        # Remove systemd service file
        service_file_path = f"/etc/systemd/system/{service_name}.service"
        if os.path.exists(service_file_path):
            subprocess.run(["sudo", "rm", service_file_path], check=True)
            console.print("Removed systemd service file.")

        # Reload systemd daemon
        console.print("Reloading systemd daemon...")
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)

        # Delete cloudflare tunnel
        console.print(f"Deleting cloudflare tunnel '{tunnel_name}'...")
        delete_tunnel_cmd = ["cloudflared", "tunnel", "delete", tunnel_name]
        result = subprocess.run(delete_tunnel_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"[green]Successfully deleted tunnel '{tunnel_name}' from Cloudflare.[/green]")
        else:
            # if the tunnel was already deleted from cloudflare, we can continue
            console.print(f"[yellow]Could not delete tunnel from Cloudflare. It might have been already deleted. Error: {result.stderr}[/yellow]")

        # Remove tunnel directory
        import shutil
        shutil.rmtree(tunnel_path)
        console.print(f"Removed tunnel directory: [cyan]{tunnel_path}[/cyan]")

        console.print(f"[green]Tunnel '{tunnel_name}' deleted successfully.[/green]")

    except subprocess.CalledProcessError as e:
        console.print("[red]Error deleting tunnel:[/red]")
        console.print(e.stderr)
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")


def display_tunnel_info():
    console.clear()
    console.print(Panel("Display Tunnel Info", style="bold yellow"))

    tunnels = [
        tunnel_name
        for tunnel_name in os.listdir(TUNNELS_DIR)
        if os.path.isdir(os.path.join(TUNNELS_DIR, tunnel_name))
    ]

    if not tunnels:
        console.print("[yellow]No tunnels found.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    tunnel_menu = TerminalMenu(tunnels, title="Select a tunnel:")
    tunnel_index = tunnel_menu.show()

    if tunnel_index is None:
        return

    selected_tunnel = tunnels[tunnel_index]
    service_name = f"cloudflare-tunnel-{selected_tunnel}"

    while True:
        console.clear()
        console.print(Panel(f"Managing Tunnel: {selected_tunnel}", style="bold yellow"))

        # Check service status
        try:
            status_check = subprocess.run(
                ["systemctl", "is-active", service_name], capture_output=True, text=True
            )
            status = status_check.stdout.strip()
            if status == "active":
                console.print(f"Service Status: [green]● active[/green]")
            else:
                console.print(f"Service Status: [red]● inactive[/red]")
        except FileNotFoundError:
            console.print("Could not check service status. 'systemctl' not found.")


        menu_items = ["Activate Service", "Deactivate Service", "View Config", "Back"]
        action_menu = TerminalMenu(menu_items, title="Actions:")
        action_index = action_menu.show()

        if action_index == 0:  # Activate
            try:
                console.print(f"Activating service for {selected_tunnel}...")
                subprocess.run(["sudo", "systemctl", "enable", "--now", service_name], check=True)
                console.print(f"[green]Service for {selected_tunnel} activated.[/green]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error activating service: {e}[/red]")
        elif action_index == 1:  # Deactivate
            try:
                console.print(f"Deactivating service for {selected_tunnel}...")
                subprocess.run(["sudo", "systemctl", "disable", "--now", service_name], check=True)
                console.print(f"[yellow]Service for {selected_tunnel} deactivated.[/yellow]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error deactivating service: {e}[/red]")
        elif action_index == 2:  # View Config
            config_path = os.path.join(TUNNELS_DIR, selected_tunnel, "config.yml")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config_content = f.read()
                console.print(Panel(config_content, title=f"Config for {selected_tunnel}", border_style="blue"))
            else:
                console.print(f"[red]Config file not found for {selected_tunnel}.[/red]")
        elif action_index == 3 or action_index is None:  # Back
            break
        Prompt.ask("\nPress Enter to continue...")


def settings_menu():
    while True:
        console.clear()
        console.print(Panel("Settings", style="bold magenta"))
        console.print(f"Current tunnel config directory: [cyan]{settings['tunnels_dir']}[/cyan]")
        menu_items = ["Change tunnel config directory", "Cloudflare login", "Back"]
        menu = TerminalMenu(menu_items, title="Settings:")
        idx = menu.show()
        if idx == 0:
            new_dir = Prompt.ask("Enter new directory for tunnel configs", default=settings['tunnels_dir'])
            if new_dir:
                settings['tunnels_dir'] = new_dir
                save_settings(settings)
                global TUNNELS_DIR
                TUNNELS_DIR = new_dir
                if not os.path.exists(TUNNELS_DIR):
                    os.makedirs(TUNNELS_DIR)
                console.print(f"[green]Tunnel config directory changed to {new_dir}[/green]")
                Prompt.ask("Press Enter to continue...")
        elif idx == 1:
            console.print("[yellow]Launching 'cloudflared login'...[/yellow]")
            try:
                subprocess.run(["cloudflared", "login"], check=True)
                console.print("[green]Cloudflare login completed.[/green]")
            except Exception as e:
                console.print(f"[red]Cloudflare login failed: {e}[/red]")
            Prompt.ask("Press Enter to continue...")
        else:
            break


def main():
    if not os.path.exists(TUNNELS_DIR):
        os.makedirs(TUNNELS_DIR)

    while True:
        console.clear()
        console.print(Panel("Cloudflare Tunnel Manager", style="bold green"))
        list_tunnels()

        menu_items = [
            "1. Create a new tunnel",
            "2. Delete a tunnel",
            "3. Display tunnel info",
            "4. Settings",
            "5. Exit"
        ]
        terminal_menu = TerminalMenu(
            menu_items,
            title="\nOptions",
            menu_cursor_style=("fg_green", "bold"),
            menu_highlight_style=("bg_green", "fg_black"),
        )
        menu_entry_index = terminal_menu.show()

        if menu_entry_index == 0:
            create_tunnel()
            Prompt.ask("\nPress Enter to continue...")
        elif menu_entry_index == 1:
            delete_tunnel()
            Prompt.ask("\nPress Enter to continue...")
        elif menu_entry_index == 2:
            display_tunnel_info()
        elif menu_entry_index == 3:
            settings_menu()
        elif menu_entry_index == 4 or menu_entry_index is None:
            break


if __name__ == "__main__":
    main()
