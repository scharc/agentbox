# Vendor JavaScript Libraries

This directory contains third-party JavaScript libraries used by the Agentbox Web UI.

## Libraries

### ansi_up.min.js
- **Version**: 6.0.2
- **Purpose**: Converts ANSI escape codes to HTML for colored terminal output
- **Source**: https://github.com/drudru/ansi_up
- **NPM**: https://www.npmjs.com/package/ansi_up

## Updating Libraries

To update ansi_up to the latest version:

```bash
# Check latest version on npm
npm view ansi_up version

# Download the latest version (replace X.Y.Z with version number)
curl -sL https://cdn.jsdelivr.net/npm/ansi_up@X.Y.Z/ansi_up.min.js \
  -o /workspace/agentbox/web/static/js/vendor/ansi_up.min.js

# Or use npm if available
npm install ansi_up
cp node_modules/ansi_up/ansi_up.min.js /workspace/agentbox/web/static/js/vendor/
```

## Security Note

Always verify the integrity of downloaded libraries before deploying to production.
