# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it by:

1. **DO NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainers directly with details of the vulnerability
3. Include steps to reproduce the issue if possible

We will acknowledge receipt within 48 hours and aim to provide a fix within 7 days for critical issues.

## Security Considerations

- **API Keys**: Never commit `.env` files or API keys to version control
- **API Access**: This MCP server has full access to your Homarr instance based on the API key's permissions
- **Network**: When deploying as a container, ensure the MCP server is not exposed to untrusted networks
