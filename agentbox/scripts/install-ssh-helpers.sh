#!/bin/bash
# Install SSH convenience scripts on host machine
# These are optional wrappers around agentbox CLI commands

set -e

echo "Installing agentbox SSH helper scripts..."

# Create abox-connect wrapper
cat > /usr/local/bin/abox-connect <<'EOF'
#!/bin/bash
# Quick connect to agentbox container
# Wrapper around: agentbox connect
exec agentbox connect "$@"
EOF
chmod +x /usr/local/bin/abox-connect

# Create abox-sessions wrapper
cat > /usr/local/bin/abox-sessions <<'EOF'
#!/bin/bash
# List agentbox sessions across all containers
# Wrapper around: agentbox session list-all
exec agentbox session list-all
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
echo "  Host agentbox"
echo "      HostName your-tailscale-hostname"
echo "      User your-user"
echo "      RemoteCommand agentbox connect"
echo "      RequestTTY yes"
