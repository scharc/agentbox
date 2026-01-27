# Connecting to Services

Your agent needs to talk to a database running in another container. Or a Redis cache. Or any other Docker service on your system.

> **Note:** This feature is implemented but currently untested. Basic functionality should work, but edge cases may not be fully covered.

## The Scenario

You're developing an app that talks to PostgreSQL. Instead of running Postgres inside the Boxctl container, you run it separately - maybe it's already running for other projects, or you want to keep concerns separated.

The problem: Docker containers are isolated. By default, your Boxctl container can't reach your Postgres container.

## Network Connect

Boxctl can join your container to other Docker networks:

```bash
boxctl network available         # What containers can I connect to?
boxctl network connect postgres-dev
boxctl network list              # What am I connected to?
```

**After connecting:** The agent can reach `postgres-dev:5432` by hostname. No IP addresses. No port mapping. The containers can talk directly.

```bash
# From inside the container, the agent can now do:
psql -h postgres-dev -U myuser mydatabase
```

## Disconnecting

When you're done:

```bash
boxctl network disconnect postgres-dev
```

The Boxctl container leaves that network. Communication stops.

## Use Cases

**Development databases:** Run Postgres, MySQL, MongoDB in separate containers. Connect when needed. Disconnect when done.

**Caching layers:** Redis, Memcached running as services. Connect to test caching behavior.

**Microservices testing:** You have multiple services in containers. Connect the agent's container to test interactions.

**Clean separation:** Keep each service isolated. Only connect what you need. Principle of least privilege.

## Configuring in .boxctl.yml

For persistent connections that should always be there:

```yaml
containers:
  - name: postgres-dev
    auto_reconnect: true    # Reconnect if container restarts
```

This automatically connects on container start, and reconnects if the target container restarts.

## What It Doesn't Do

This feature connects containers on the same Docker host. It doesn't:

- Connect to remote services (use environment variables for that)
- Set up VPNs or tunnels
- Replace proper service discovery in production

It's for local development where you have multiple containers that need to talk.

## What's Next

- **[Configuration](08-configuration.md)** - All `.boxctl.yml` options
- **[CLI Reference](REF-A-cli.md)** - Full network command list
