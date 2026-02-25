---
name: docker
description: Docker automation — CLI-first, Docker Desktop Electron blindness, workarounds
requires: [docker]
install: brew install --cask docker
---

# Docker Skill

Docker Desktop is an Electron app with a **blind accessibility tree** — Nexus cannot see its UI elements. Always prefer the Docker CLI.

## CLI First (always prefer this)

```bash
# Container management
docker ps                          # List running containers
docker ps -a                       # List all containers
docker start <container>           # Start container
docker stop <container>            # Stop container
docker rm <container>              # Remove container
docker logs <container>            # View logs
docker logs -f <container>         # Follow logs
docker exec -it <container> bash   # Shell into container

# Image management
docker images                      # List images
docker pull <image>                # Pull image
docker rmi <image>                 # Remove image
docker build -t <tag> .            # Build from Dockerfile

# Docker Compose
docker compose up -d               # Start services (detached)
docker compose down                # Stop services
docker compose ps                  # List service status
docker compose logs -f             # Follow all logs
docker compose exec <svc> bash     # Shell into service

# System
docker system df                   # Disk usage
docker system prune -f             # Clean up unused resources
docker info                        # System info
docker version                     # Version info

# Network
docker network ls                  # List networks
docker network inspect bridge      # Inspect network

# Volumes
docker volume ls                   # List volumes
docker volume rm <vol>             # Remove volume
```

## Installation (CLI approach)

```bash
# Install via Homebrew (recommended)
brew install --cask docker

# Pre-approve to avoid Gatekeeper dialog
xattr -r -d com.apple.quarantine /Applications/Docker.app

# Launch
open -a Docker

# Wait for Docker daemon to be ready
while ! docker info > /dev/null 2>&1; do sleep 1; done
echo "Docker is ready"
```

## Why Docker Desktop GUI Is Blind

Docker Desktop has a **nested Electron architecture**:
- Outer wrapper: native Go binary (`com.docker.docker`)
- Inner app: Electron (`Docker Desktop.app` nested inside Docker.app)
- AXManualAccessibility set on the outer process doesn't reach the inner Electron app
- Result: only 4 window-frame elements visible, no content tree

## GUI Workarounds (when CLI isn't enough)

If you absolutely must interact with Docker Desktop GUI:

1. **Keyboard navigation**: Tab to cycle elements, Space/Enter to activate
2. **CDP approach**: Relaunch with `--remote-debugging-port=9223`
   ```bash
   osascript -e 'tell application "Docker" to quit'
   sleep 2
   open -a "/Applications/Docker.app" --args --remote-debugging-port=9223
   sleep 5
   curl http://localhost:9223/json  # List CDP targets
   ```
3. **Screenshot + coordinate click**: Last resort, unreliable

## System Dialogs During Installation

Docker's first launch triggers several macOS dialogs:
- **Gatekeeper**: "app downloaded from the internet" — prevent with `xattr -r -d com.apple.quarantine`
- **Network permission**: "find devices on local network" — cannot prevent, user must handle
- **Password prompt**: Privileged helper installation — user must enter password
- **Subscription agreement**: Inside Docker Desktop UI — keyboard Tab+Enter may work

## Common Docker Compose Patterns

```yaml
# docker-compose.yml
services:
  web:
    image: nginx
    ports: ["80:80"]
    volumes: ["./html:/usr/share/nginx/html"]
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: secret
    volumes: ["pgdata:/var/lib/postgresql/data"]
volumes:
  pgdata:
```

## Tips

- `docker compose` (v2, built-in) replaces `docker-compose` (v1, deprecated)
- Docker Desktop settings can be edited directly: `~/.docker/daemon.json`
- To restart Docker daemon without GUI: `killall Docker && open -a Docker`
- Docker contexts let you manage remote Docker hosts from local CLI
- `lazydocker` (TUI) is a great alternative to Docker Desktop GUI: `brew install lazydocker`
