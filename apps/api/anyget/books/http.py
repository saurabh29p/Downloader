"""GET helpers for adapters: JSON or XML through Net, with clear errors."""

from typing import Any
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as SafeET

from anyget.books.base import SearchContext
from anyget.handlers.base import HandlerError


async def get_json(ctx: SearchContext, url: str, headers: dict[str, str] | None = None) -> Any:
    response = await ctx.net.request("GET", url, headers=headers)
    if response.status_code in (401, 403):
        raise HandlerError("needs_key", f"{response.url.host} refused the request (key?)")
    if response.status_code >= 400:
        raise HandlerError("upstream", f"{response.url.host} answered {response.status_code}")
    return response.json()


async def get_xml(ctx: SearchContext, url: str) -> Element:
    response = await ctx.net.request("GET", url)
    if response.status_code >= 400:
        raise HandlerError("upstream", f"{response.url.host} answered {response.status_code}")
    root: Element = SafeET.fromstring(response.content)
    return root


async def get_text(ctx: SearchContext, url: str) -> str:
    response = await ctx.net.request("GET", url)
    if response.status_code >= 400:
        raise HandlerError("upstream", f"{response.url.host} answered {response.status_code}")
    return response.text


def local(tag: str) -> str:
    """XML tag without its namespace."""
    return tag.rsplit("}", 1)[-1]


def children(node: Element, name: str) -> list[Element]:
    return [c for c in node.iter() if local(c.tag) == name]


def text_of(node: Element, name: str) -> str | None:
    for child in node.iter():
        if local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def texts_of(node: Element, name: str) -> list[str]:
    return [
        c.text.strip() for c in node.iter() if local(c.tag) == name and c.text and c.text.strip()
    ]
