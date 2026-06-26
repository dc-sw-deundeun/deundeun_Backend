from app.core.client_ip import resolve_client_ip


def test_ignores_forwarded_for_when_proxy_is_disabled() -> None:
    client_ip = resolve_client_ip(
        direct_client_host="203.0.113.10",
        forwarded_for="198.51.100.1",
        trusted_proxy=False,
        trusted_proxy_cidrs=["203.0.113.0/24"],
    )

    assert client_ip == "203.0.113.10"


def test_ignores_forwarded_for_without_trusted_proxy_cidr() -> None:
    client_ip = resolve_client_ip(
        direct_client_host="203.0.113.10",
        forwarded_for="198.51.100.1",
        trusted_proxy=True,
        trusted_proxy_cidrs=[],
    )

    assert client_ip == "203.0.113.10"


def test_ignores_forwarded_for_from_untrusted_proxy_source() -> None:
    client_ip = resolve_client_ip(
        direct_client_host="203.0.113.10",
        forwarded_for="198.51.100.1",
        trusted_proxy=True,
        trusted_proxy_cidrs=["10.0.0.0/8"],
    )

    assert client_ip == "203.0.113.10"


def test_uses_forwarded_for_from_trusted_proxy_source() -> None:
    client_ip = resolve_client_ip(
        direct_client_host="10.0.0.10",
        forwarded_for="198.51.100.1, 10.0.0.10",
        trusted_proxy=True,
        trusted_proxy_cidrs=["10.0.0.0/8"],
    )

    assert client_ip == "198.51.100.1"


def test_ignores_invalid_forwarded_for_value() -> None:
    client_ip = resolve_client_ip(
        direct_client_host="10.0.0.10",
        forwarded_for="not-an-ip",
        trusted_proxy=True,
        trusted_proxy_cidrs=["10.0.0.0/8"],
    )

    assert client_ip == "10.0.0.10"
