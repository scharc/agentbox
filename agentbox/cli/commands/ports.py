# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Port forwarding commands."""

import os
import socket
from pathlib import Path

import click

from agentbox.cli import cli
from agentbox.cli.helpers import _get_project_context, console, handle_errors
from agentbox.config import parse_port_spec, validate_host_port, ProjectConfig
from agentbox.utils.project import resolve_project_dir


def _get_agentboxd_socket_path() -> Path:
    """Get the agentboxd socket path."""
    return Path(f"/run/user/{os.getuid()}/agentboxd/agentboxd.sock")


def _send_agentboxd_command(command: dict) -> dict:
    """Send a command to agentboxd and get response."""
    import json

    socket_path = _get_agentboxd_socket_path()
    if not socket_path.exists():
        raise RuntimeError("agentboxd not running. Start with: agentbox service start")

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(socket_path))
        sock.settimeout(5.0)
        sock.sendall((json.dumps(command) + "\n").encode())

        # Read response
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk

        if data:
            return json.loads(data.decode().strip())
        return {"ok": False, "error": "No response from agentboxd"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        sock.close()


def _get_container_name() -> str:
    """Get the container name for the current project."""
    return _get_project_context().container_name


@cli.group()
def ports():
    """Manage port forwarding (list, add, remove).

    Forward ports between host and container without rebuilds.

    Commands:
      expose    - Expose container port to host (service runs in container)
      forward   - Forward host port into container (service runs on host)
      unexpose  - Remove an exposed port
      unforward - Remove a forwarded port
    """
    pass


@ports.command(name="list")
@handle_errors
def ports_list():
    """List all port forwarding configurations."""
    project_dir = resolve_project_dir()

    config = ProjectConfig(project_dir)

    # Get configured ports from .agentbox.yml
    host_ports = config.ports_host
    container_ports = config.ports_container

    console.print("[bold]Port Configuration[/bold]\n")

    # Exposed ports (container -> host)
    console.print("[cyan]Exposed Ports[/cyan] (container → host)")
    if host_ports:
        for spec in host_ports:
            parsed = parse_port_spec(spec)
            if parsed["host_port"] == parsed["container_port"]:
                console.print(f"  container:{parsed['container_port']} → host:{parsed['host_port']}")
            else:
                console.print(f"  container:{parsed['container_port']} → host:{parsed['host_port']}")
    else:
        console.print("  [dim]No exposed ports[/dim]")

    console.print()

    # Forwarded ports (host -> container)
    console.print("[cyan]Forwarded Ports[/cyan] (host → container)")
    if container_ports:
        for entry in container_ports:
            # Handle both old dict format and new string format
            if isinstance(entry, dict):
                host_port = entry.get("port", 0)
                container_port = entry.get("container_port", host_port)
            else:
                parts = str(entry).split(":")
                if len(parts) == 2:
                    host_port, container_port = int(parts[0]), int(parts[1])
                else:
                    host_port = container_port = int(parts[0])
            console.print(f"  host:{host_port} → container:{container_port}")
    else:
        console.print("  [dim]No forwarded ports[/dim]")

    console.print()
    console.print("[dim]Add ports: abox ports expose <port> or abox ports forward <port>[/dim]")


@ports.command(name="expose")
@click.argument("port_spec")
@handle_errors
def expose(port_spec: str):
    """Expose a container port to the host.

    PORT_SPEC format is container:host (source:destination):
      3000       - Expose container:3000 on host:3000
      3000:8080  - Expose container:3000 on host:8080

    Use this when your service runs INSIDE the container and you
    want to access it from the host (e.g., browser at localhost:8080).

    Note: Host ports below 1024 require root and are not allowed.
    """
    # Parse as container:host format
    parts = port_spec.split(":")
    if len(parts) == 1:
        container_port = host_port = int(parts[0])
    elif len(parts) == 2:
        container_port = int(parts[0])
        host_port = int(parts[1])
    else:
        raise click.ClickException(f"Invalid port format: {port_spec}. Use 'port' or 'container:host'")

    # Validate host port
    validate_host_port(host_port)

    # Load and update config
    project_dir = resolve_project_dir()

    config = ProjectConfig(project_dir)
    if not config.exists():
        raise click.ClickException("No .agentbox.yml found. Run: agentbox init")

    # Check if already configured (config stores host:container format internally)
    current_ports = config.ports_host
    for existing in current_ports:
        existing_parsed = parse_port_spec(existing)
        if existing_parsed["host_port"] == host_port:
            console.print(f"[yellow]Host port {host_port} already exposed[/yellow]")
            return

    # Update config - store in host:container format for backward compatibility
    raw_ports = config.config.get("ports", {})
    if isinstance(raw_ports, list):
        raw_ports = {"host": raw_ports, "container": []}

    if "host" not in raw_ports:
        raw_ports["host"] = []

    # Store as host:container format
    if host_port == container_port:
        storage_spec = str(host_port)
    else:
        storage_spec = f"{host_port}:{container_port}"
    raw_ports["host"].append(storage_spec)
    config.config["ports"] = raw_ports
    config.save()

    # Try to add to running proxy (dynamically, no rebuild needed)
    container_name = _get_container_name()
    response = _send_agentboxd_command({
        "action": "add_host_port",
        "container": container_name,
        "host_port": host_port,
        "container_port": container_port,
    })

    if response.get("ok"):
        console.print(f"[green]✓ Exposed container:{container_port} → host:{host_port}[/green]")
        if response.get("message"):
            console.print(f"[dim]{response.get('message')}[/dim]")
    elif "No response" in response.get("error", "") or "not running" in response.get("error", ""):
        console.print("[yellow]Port saved to config. Start proxy with: agentbox service start[/yellow]")
    else:
        error = response.get("error", "")
        console.print(f"[yellow]Port saved to config but could not activate now:[/yellow]")
        console.print(f"[red]{error}[/red]")

        # Provide helpful guidance for Docker conflicts
        if "Docker" in error or "in use" in error.lower():
            console.print("\n[bold]To fix this:[/bold]")
            console.print("  1. Add 'mode: tunnel' under 'ports:' in .agentbox.yml")
            console.print("  2. Run: abox rebuild")
            console.print("  3. The port will be exposed via tunnel instead of Docker")


@ports.command(name="forward")
@click.argument("port_spec")
@handle_errors
def forward(port_spec: str):
    """Forward a host port into the container.

    PORT_SPEC format:
      9222       - Forward host:9222 to container:9222
      9222:9223  - Forward host:9222 to container:9223

    Use this when your service runs ON THE HOST and you want
    to access it from inside the container (e.g., host MCP servers).

    Example: abox ports forward 9222
    """
    # Parse port spec
    parts = port_spec.split(":")
    if len(parts) == 1:
        port = container_port = int(parts[0])
    elif len(parts) == 2:
        port = int(parts[0])
        container_port = int(parts[1])
    else:
        raise click.ClickException(f"Invalid port format: {port_spec}. Use 'port' or 'host:container'")

    # Load and update config
    project_dir = resolve_project_dir()

    config = ProjectConfig(project_dir)
    if not config.exists():
        raise click.ClickException("No .agentbox.yml found. Run: agentbox init")

    # Check if already configured
    current_ports = config.ports_container
    for entry in current_ports:
        existing_port = entry.get("port") if isinstance(entry, dict) else int(str(entry).split(":")[0])
        if existing_port == port:
            console.print(f"[yellow]Port {port} already forwarded[/yellow]")
            return

    # Update config - store as simple port spec string (like host ports)
    raw_ports = config.config.get("ports", {})
    if isinstance(raw_ports, list):
        raw_ports = {"host": raw_ports, "container": []}

    if "container" not in raw_ports:
        raw_ports["container"] = []

    # Store as "port" or "host:container" string
    raw_ports["container"].append(port_spec)
    config.config["ports"] = raw_ports
    config.save()

    console.print(f"[green]✓ Forwarding host:{port} → container:{container_port}[/green]")

    # Try to dynamically add the listener via proxy socket
    container_name = _get_container_name()
    response = _send_agentboxd_command({
        "action": "add_container_port",
        "container": container_name,
        "host_port": port,
        "container_port": container_port,
    })

    if response.get("ok"):
        console.print(f"[green]✓ Listener active now on container:{container_port}[/green]")
    elif "not connected" in response.get("error", ""):
        console.print("[blue]Tunnel client not connected. Will be active when container starts.[/blue]")
    else:
        console.print("[yellow]Could not add listener dynamically. Will be active on container restart.[/yellow]")


@ports.command(name="unexpose")
@click.argument("port", type=int)
@handle_errors
def unexpose(port: int):
    """Remove an exposed port.

    PORT is the host port number to stop exposing.
    """
    project_dir = resolve_project_dir()

    config = ProjectConfig(project_dir)
    if not config.exists():
        raise click.ClickException("No .agentbox.yml found")

    # Find and remove matching port spec
    raw_ports = config.config.get("ports", {})
    if isinstance(raw_ports, list):
        raw_ports = {"host": raw_ports, "container": []}

    host_ports = raw_ports.get("host", [])
    found = False
    new_host_ports = []

    for spec in host_ports:
        parsed = parse_port_spec(spec)
        if parsed["host_port"] == port:
            found = True
        else:
            new_host_ports.append(spec)

    if not found:
        console.print(f"[yellow]Port {port} not exposed[/yellow]")
        return

    raw_ports["host"] = new_host_ports
    config.config["ports"] = raw_ports
    config.save()

    # Try to remove from running proxy
    container_name = _get_container_name()
    response = _send_agentboxd_command({
        "action": "remove_host_port",
        "container": container_name,
        "host_port": port,
    })

    if response.get("ok"):
        console.print(f"[green]✓ Unexposed port {port}[/green]")
        console.print(f"[green]✓ Listener stopped[/green]")
    else:
        error = response.get("error", "")
        if "not connected" in error:
            console.print(f"[green]✓ Unexposed port {port}[/green]")
            console.print("[blue]Container not connected. Config updated.[/blue]")
        else:
            console.print(f"[green]✓ Unexposed port {port} (config updated)[/green]")


@ports.command(name="unforward")
@click.argument("port", type=int)
@handle_errors
def unforward(port: int):
    """Remove a forwarded port.

    PORT is the host port number to stop forwarding.
    """
    project_dir = resolve_project_dir()

    config = ProjectConfig(project_dir)
    if not config.exists():
        raise click.ClickException("No .agentbox.yml found")

    # Find and remove matching entry
    raw_ports = config.config.get("ports", {})
    if isinstance(raw_ports, list):
        raw_ports = {"host": raw_ports, "container": []}

    container_ports = raw_ports.get("container", [])
    found = False
    new_container_ports = []

    for entry in container_ports:
        # Handle both old dict format and new string format
        if isinstance(entry, dict):
            entry_port = entry.get("port", 0)
        else:
            entry_port = int(str(entry).split(":")[0])

        if entry_port == port:
            found = True
        else:
            new_container_ports.append(entry)

    if not found:
        console.print(f"[yellow]Port {port} not forwarded[/yellow]")
        return

    raw_ports["container"] = new_container_ports
    config.config["ports"] = raw_ports
    config.save()

    console.print(f"[green]✓ Unforwarded port {port}[/green]")

    # Try to dynamically remove the listener via proxy socket
    container_name = _get_container_name()
    response = _send_agentboxd_command({
        "action": "remove_container_port",
        "container": container_name,
        "host_port": port,
    })

    if response.get("ok"):
        console.print(f"[green]✓ Listener stopped[/green]")
    elif "not connected" in response.get("error", ""):
        console.print("[blue]Container not connected. Config updated.[/blue]")
    else:
        console.print("[yellow]Listener will stop on container restart.[/yellow]")


@ports.command(name="status")
@handle_errors
def ports_status():
    """Show active port tunnels (runtime status)."""
    import json
    import urllib.request
    import urllib.error
    from agentbox.host_config import HostConfig

    # Try to get status from web API
    try:
        host_config = HostConfig()
        web_config = host_config._config.get("web_server", {})
        port = web_config.get("port", 8080)

        url = f"http://localhost:{port}/api/status"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})

        with urllib.request.urlopen(req, timeout=2) as response:
            status = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception):
        console.print("[yellow]Could not connect to agentboxd. Is the service running?[/yellow]")
        console.print("[dim]Start with: agentbox service start[/dim]")
        return

    console.print("[bold]Active Port Tunnels[/bold]\n")

    # SSH tunnel stats
    tunnels = status.get("tunnels", {})
    ssh_stats = tunnels.get("ssh_tunnel", {})
    connected = ssh_stats.get("connected_containers", 0)
    forwards = ssh_stats.get("total_forwards", 0)

    console.print("[cyan]SSH Tunnel Status[/cyan]")
    if connected > 0:
        console.print(f"  [green]●[/green] {connected} container(s) connected")
        console.print(f"    {forwards} active port forward(s)")
    else:
        console.print("  [dim]No containers connected[/dim]")

    console.print()

    # Connected containers
    service = status.get("service", {})
    containers = service.get("connected_containers", [])
    if containers:
        console.print("[cyan]Connected Containers[/cyan]")
        for name in containers:
            console.print(f"  [green]●[/green] {name}")
        console.print()

    # Show configured ports from containers
    container_list = status.get("containers", [])
    console.print("[cyan]Container Ports[/cyan]")
    has_ports = False
    for c in container_list:
        if c.get("status") != "running":
            continue
        project_path = c.get("project_path", "")
        if project_path:
            from agentbox.config import ProjectConfig
            config = ProjectConfig(Path(project_path))
            if config.exists():
                host_ports = config.ports_host
                if host_ports:
                    has_ports = True
                    name = c.get("project", c.get("name", "?"))
                    console.print(f"  [bold]{name}[/bold]")
                    for spec in host_ports:
                        try:
                            parsed = parse_port_spec(spec)
                            console.print(f"    :{parsed['host_port']} ← container:{parsed['container_port']}")
                        except (ValueError, KeyError):
                            console.print(f"    [dim]{spec} (invalid)[/dim]")
    if not has_ports:
        console.print("  [dim]No exposed ports configured[/dim]")


# Backward compatibility aliases (hidden from help)
@ports.group(name="add", hidden=True)
def ports_add():
    """[Deprecated] Use 'expose' or 'forward' instead."""
    pass


@ports_add.command(name="host")
@click.argument("port_spec")
@handle_errors
def add_host(port_spec: str):
    """[Deprecated] Use 'abox ports expose' instead."""
    console.print("[yellow]Note: 'abox ports add host' is deprecated. Use 'abox ports expose' instead.[/yellow]\n")
    # Parse old format (host:container) and convert to new format (container:host)
    parsed = parse_port_spec(port_spec)
    if parsed["host_port"] == parsed["container_port"]:
        new_spec = str(parsed["container_port"])
    else:
        new_spec = f"{parsed['container_port']}:{parsed['host_port']}"
    ctx = click.get_current_context()
    ctx.invoke(expose, port_spec=new_spec)


@ports_add.command(name="container")
@click.argument("name")
@click.argument("port", type=int)
@click.argument("container_port", type=int, required=False)
@handle_errors
def add_container(name: str, port: int, container_port: int = None):
    """[Deprecated] Use 'abox ports forward' instead."""
    console.print("[yellow]Note: 'abox ports add container' is deprecated. Use 'abox ports forward' instead.[/yellow]\n")
    # Convert old format to new port_spec format
    if container_port and container_port != port:
        port_spec = f"{port}:{container_port}"
    else:
        port_spec = str(port)
    ctx = click.get_current_context()
    ctx.invoke(forward, port_spec=port_spec)


@ports.group(name="remove", hidden=True)
def ports_remove():
    """[Deprecated] Use 'unexpose' or 'unforward' instead."""
    pass


@ports_remove.command(name="host")
@click.argument("port", type=int)
@handle_errors
def remove_host(port: int):
    """[Deprecated] Use 'abox ports unexpose' instead."""
    console.print("[yellow]Note: 'abox ports remove host' is deprecated. Use 'abox ports unexpose' instead.[/yellow]\n")
    ctx = click.get_current_context()
    ctx.invoke(unexpose, port=port)


@ports_remove.command(name="container")
@click.argument("name_or_port")
@handle_errors
def remove_container(name_or_port: str):
    """[Deprecated] Use 'abox ports unforward' instead."""
    console.print("[yellow]Note: 'abox ports remove container' is deprecated. Use 'abox ports unforward' instead.[/yellow]\n")
    # Try to parse as port number
    try:
        port = int(name_or_port)
    except ValueError:
        console.print(f"[red]Port must be a number, got: {name_or_port}[/red]")
        return
    ctx = click.get_current_context()
    ctx.invoke(unforward, port=port)
