# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Nemlig Shopper, please report it responsibly:

1. **Do not** open a public GitHub issue
2. **Email** the maintainer directly or use GitHub's private vulnerability reporting feature
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to understand and address the issue.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | Yes       |
| < 1.0   | No        |

## Security Considerations

### Credential Storage

Nemlig Shopper stores credentials locally when you use `nemlig login`:

- **Location**: `~/.nemlig-shopper/credentials.json`
- **Permissions**: File is created with `chmod 600` (owner read/write only)
- **Format**: Plain JSON with email and password

**Recommendations**:
- Use environment variables (`.env` file) instead of saved credentials when possible
- Add `.env` to your global `.gitignore`
- Never commit credentials to version control
- Use `nemlig logout` to remove saved credentials when no longer needed

### Environment Variables

Credentials can be provided via environment variables:

```bash
export NEMLIG_USERNAME="your-email@example.com"
export NEMLIG_PASSWORD="your-password"
```

Or in a `.env` file (automatically loaded by the CLI).

### API Communication

- All communication with Nemlig.com uses HTTPS
- JWT tokens are used for session management
- Tokens are stored in memory only (not persisted)

### What We Don't Do

- We don't send your credentials anywhere except Nemlig.com
- We don't log passwords or sensitive data
- We don't store session tokens on disk
- We don't include analytics or telemetry

## Scope

### In Scope

- Authentication and credential handling
- API communication security
- Local file permission issues
- Injection vulnerabilities (command, path traversal, etc.)

### Out of Scope

- Vulnerabilities in Nemlig.com's API (report to Nemlig directly)
- Issues requiring physical access to the user's machine
- Social engineering attacks
- Denial of service

## Best Practices for Users

1. **Keep your system updated** - Ensure Python and dependencies are current
2. **Use a virtual environment** - Isolate project dependencies
3. **Review `.env` files** - Never share or commit them
4. **Monitor your Nemlig account** - Check for unauthorized orders
5. **Use strong passwords** - For your Nemlig.com account

## Dependency Security

We use automated tools to monitor dependencies:

- Dependabot alerts (GitHub)
- Regular `uv` updates

To check for known vulnerabilities in dependencies:

```bash
uv pip audit
```

## Acknowledgments

We appreciate responsible disclosure and will credit security researchers (with permission) for any vulnerabilities they help us fix.
