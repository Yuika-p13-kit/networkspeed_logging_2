# LAN host name design

## Intent

Keep Raspberry Pi access stable when its DHCP-assigned IP address changes. Access is limited to the home LAN; remote access is out of scope.

## Approaches

- **Avahi/mDNS (selected):** Advertise a stable host name such as `network-speed-pi.local`. This avoids a router-specific setup and works naturally with the Mac client. The existing README says `raspberrypi.local` did not resolve, so the Pi's hostname/service and actual LAN resolution must be checked before treating this as established.
- **Router local DNS:** Register a stable DNS name in the router and use it for SSH, HTTPS, and deployment. This is the fallback if multicast DNS is unavailable on this LAN; it depends on router features and configuration.

Use mDNS first and document router DNS as the fallback. Do not use a hard-coded IP as the normal connection path.

## Scope and constraints

- Pi-side hostname/Avahi configuration and verification instructions.
- Use the chosen DNS name for SSH, deployment, dashboard, and API instructions.
- Generate the local HTTPS certificate with the DNS name in its subject alternative names (SAN), so name-based HTTPS validation works.
- Keep a concise fallback procedure for router local DNS and document how to diagnose failed mDNS resolution.
- Do not configure or add remote-access services.
- Existing unrelated working-tree changes must remain untouched.

## Acceptance criteria

1. From the Mac on the home LAN, the chosen hostname resolves to the Pi after its IP address changes.
2. SSH and deployment target the hostname rather than an IP literal.
3. HTTPS dashboard and `/api/dashboard/latest` work through `https://<hostname>.local:8443/` with the hostname covered by the certificate SAN.
4. README/runbook explain Pi-side setup, Mac-side verification, and the router-DNS fallback if mDNS is blocked.

## Open implementation detail

Confirm the Pi's current hostname and whether Avahi is installed and enabled before selecting the final `.local` name. Verify end-to-end against the real Pi; local configuration alone does not establish that the LAN advertises or resolves the name.
