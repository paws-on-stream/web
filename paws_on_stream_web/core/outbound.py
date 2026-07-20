import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeOutboundUrlError(ValueError):
    pass


def validate_public_https_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise UnsafeOutboundUrlError("Only public HTTPS URLs are allowed.")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        }
    except socket.gaierror as exc:
        raise UnsafeOutboundUrlError("The configured host cannot be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise UnsafeOutboundUrlError("Private or non-global hosts are not allowed.")
    return url
