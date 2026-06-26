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
        forwarded_client = _client_ip_from_forwarded_chain(
            forwarded_for=forwarded_for,
            direct_client_host=direct_client_host,
            trusted_proxy_cidrs=trusted_proxy_cidrs,
        )
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


def _client_ip_from_forwarded_chain(
    *,
    forwarded_for: str,
    direct_client_host: str,
    trusted_proxy_cidrs: list[str],
) -> str | None:
    chain = [
        item
        for item in [*_parse_forwarded_for(forwarded_for), direct_client_host]
        if item is not None
    ]
    for candidate in reversed(chain):
        if not _is_trusted_proxy_source(candidate, trusted_proxy_cidrs):
            return candidate
    return None


def _parse_forwarded_for(forwarded_for: str) -> list[str]:
    forwarded_ips: list[str] = []
    for raw_ip in forwarded_for.split(","):
        candidate = raw_ip.strip()
        if not candidate:
            continue
        try:
            ip_address(candidate)
        except ValueError:
            continue
        forwarded_ips.append(candidate)
    return forwarded_ips
