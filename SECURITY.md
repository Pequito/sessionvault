# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

Only the latest commit on main is supported.

## Reporting a Vulnerability

- Open a **private** issue (preferred) or email pequito [at] users.noreply.github.com
- Describe: vulnerability type, steps to reproduce, impact (CVSS if known), suggested fix (optional)

We acknowledge reports within 48 hours and update every 7 days.

Do **not** disclose publicly until fixed (responsible disclosure).

## Vulnerability Disclosure Timeline (Best Practices)

- **Day 0** — Report received  
- **Day 0–2** — Acknowledgment & initial triage  
- **Day 3–14** — Reproduction, severity assessment  
- **Day 15–90** — Fix development & testing (target 30–90 days; critical faster, complex longer)  
- **Day 91–120** — Coordinated release/patch + optional grace period for users  
- **Day 121+** — Public disclosure (after fix released or max 120 days from report; mutual agreement may extend)

Inspired by OWASP, CERT/CC, CISA, and industry norms (e.g., 90-day standard for many vendors). Timelines flexible based on severity/complexity.

## Security Considerations

- KeePass encryption depends on strong master password  
- No credentials sent over network  
- Stored only in KeePass file  
- Third-party tools (xfreerdp, vncviewer) run locally — review their security

MIT licensed. No bounty program (yet).
