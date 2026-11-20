"""AI Video Clipper Core Package"""
from core.dns_patch import apply_secure_dns

# Apply Secure DNS patch globally to bypass poisoned network DNS
apply_secure_dns()
