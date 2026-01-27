#!/bin/bash
# Install SSH convenience scripts on host machine
# These are optional wrappers around boxctl CLI commands

set -e

echo "Installing boxctl SSH helper scripts..."

# Create abox-connect wrapper
cat > /usr/local/bin/abox-connect <<'EOF'
#!/bin/bash
# Quick connect to boxctl container
# Wrapper around: boxctl connect
exec boxctl connect "$@"
EOF
chmod +x /usr/local/bin/abox-connect

# Create abox-sessions wrapper
cat > /usr/local/bin/abox-sessions <<'EOF'
#!/bin/bash
# List boxctl sessions across all containers
# Wrapper around: boxctl session list-all
exec boxctl session list-all
EOF
chmod +x /usr/local/bin/abox-sessions

echo "✓ SSH helpers installed successfully!"
echo ""
echo "Available commands:"
echo "  abox-connect [project] [-s session]  - Connect to container"
echo "  abox-sessions                         - List all sessions"
echo ""
echo "Examples:"
echo "  abox-connect                    # Connect to current project"
echo "  abox-connect my-project         # Connect to specific project"
echo "  abox-connect -s claude          # Attach to claude session"
echo "  abox-connect -l                 # List sessions in current project"
echo "  abox-sessions                   # List sessions across all projects"
echo ""
echo "Tip: Add to ~/.ssh/config for direct SSH access:"
echo "  Host boxctl"
echo "      HostName your-tailscale-hostname"
echo "      User your-user"
echo "      RemoteCommand boxctl connect"
echo "      RequestTTY yes"
