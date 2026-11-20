"""
Secure DNS-over-HTTPS (DoH) patch for bypassing poisoned/blocked local DNS on YouTube domains.
"""
import socket
import requests
from typing import Dict, List

_dns_cache: Dict[str, List[str]] = {}
_orig_getaddrinfo = socket.getaddrinfo

YOUTUBE_DOMAINS = (
    "youtube.com",
    "googlevideo.com",
    "ytimg.com",
    "youtu.be",
    "google.com",
    "ggpht.com"
)

def doh_resolve(hostname: str) -> List[str]:
    """Resolve hostname using Cloudflare DNS-over-HTTPS (DoH)."""
    if hostname in _dns_cache:
        return _dns_cache[hostname]

    try:
        url = f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A"
        r = requests.get(url, headers={"accept": "application/dns-json"}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
            if ips:
                _dns_cache[hostname] = ips
                return ips
    except Exception:
        pass

    # Secondary DoH fallback (Google)
    try:
        url = f"https://dns.google/resolve?name={hostname}&type=A"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
            if ips:
                _dns_cache[hostname] = ips
                return ips
    except Exception:
        pass

    return []

def secure_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Intercept socket.getaddrinfo and route YouTube domains through DoH."""
    if host and any(domain in str(host) for domain in YOUTUBE_DOMAINS):
        ips = doh_resolve(str(host))
        if ips:
            results = []
            for ip in ips:
                try:
                    res = _orig_getaddrinfo(ip, port, socket.AF_INET, type, proto, flags)
                    results.extend(res)
                except Exception:
                    pass
            if results:
                return results

    return _orig_getaddrinfo(host, port, family, type, proto, flags)

def apply_secure_dns():
    """Apply the DoH patch globally."""
    socket.getaddrinfo = secure_getaddrinfo
