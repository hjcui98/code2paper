"""OS boundary checks for offline qualification, never normal/live admission.

The parent namespace identity must come from the original suite owner's bound
core plan. Environment flags and declarations that a provider is fake are not
network authority. All domain/send/fee gates still belong to the usual owners.
"""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

from .protocol import ProtocolError


def network_namespace_identity() -> dict[str, int]:
    status=os.stat('/proc/self/ns/net')
    return {'device':status.st_dev,'inode':status.st_ino}


def assert_offline_qualification_namespace(parent_identity: object) -> dict[str, int]:
    if (not isinstance(parent_identity,dict) or set(parent_identity) != {'device','inode'}
            or any(type(parent_identity[key]) is not int or parent_identity[key] <= 0
                   for key in ('device','inode'))):
        raise ProtocolError('qualification_parent_namespace_invalid')
    current=network_namespace_identity()
    if current == parent_identity:
        raise ProtocolError('qualification_network_not_isolated')
    interfaces=[line.split(':',1)[0].strip()
        for line in Path('/proc/net/dev').read_text().splitlines()[2:] if ':' in line]
    if interfaces != ['lo']:
        raise ProtocolError('qualification_network_not_isolated')
    return current


def assert_frozen_loopback_provider(launch: object) -> None:
    if not isinstance(launch,dict):raise ProtocolError('qualification_provider_invalid')
    config=launch.get('provider_config')
    providers=config.get('providers') if isinstance(config,dict) else None
    if not isinstance(providers,dict) or not providers:
        raise ProtocolError('qualification_provider_invalid')
    for profile in providers.values():
        if not isinstance(profile,dict) or not isinstance(profile.get('baseURL'),str):
            raise ProtocolError('qualification_provider_invalid')
        try:
            endpoint=urlsplit(profile['baseURL'])
            address=ipaddress.ip_address(endpoint.hostname or '')
            valid=(endpoint.scheme in {'http','https'} and address.is_loopback
                and endpoint.port is not None and 0 < endpoint.port < 65536
                and endpoint.username is None and endpoint.password is None
                and not endpoint.query and not endpoint.fragment)
        except ValueError:
            valid=False
        if not valid:raise ProtocolError('qualification_provider_not_loopback')
