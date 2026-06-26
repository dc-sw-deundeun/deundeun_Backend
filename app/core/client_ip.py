from ipaddress import ip_address, ip_network


def resolve_client_ip(
    *,
    direct_client_host: str | None,
    forwarded_for: str | None,
    trusted_proxy: bool,
    trusted_proxy_cidrs: list[str],
) -> str:
    if (
        trusted_proxy
        and forwarded_for
        and _is_trusted_proxy_source(direct_client_host, trusted_proxy_cidrs)
    ):
        forwarded_client = _first_forwarded_ip(forwarded_for)
        if forwarded_client is not None:
            return forwarded_client

    return direct_client_host or "unknown"


def _is_trusted_proxy_source(
    direct_client_host: str | None,
    trusted_proxy_cidrs: list[str],
) -> bool:
    if direct_client_host is None or not trusted_proxy_cidrs:
        return False

    try:
        client_ip = ip_address(direct_client_host)
    except ValueError:
        return False

    for cidr in trusted_proxy_cidrs:
        try:
            if client_ip in ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def _first_forwarded_ip(forwarded_for: str) -> str | None:
    first = forwarded_for.split(",", 1)[0].strip()
    if not first:
        return None
    try:
        ip_address(first)
    except ValueError:
        return None
    return first
