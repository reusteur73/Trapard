from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generic, Iterable, Protocol, TypeVar, Union, Optional
from discord.ext import commands
import asyncio
import discord
import io


if TYPE_CHECKING:
    from bot import Trapard
    from aiohttp import ClientSession
    from types import TracebackType


T = TypeVar('T')


# For typing purposes, `Context.db` returns a Protocol type
# that allows us to properly type the return values via narrowing
# Right now, asyncpg is untyped so this is better than the current status quo
# To actually receive the regular Pool type `Context.pool` can be used instead.

class Context(commands.Context):
    channel: Union[discord.VoiceChannel, discord.TextChannel, discord.Thread, discord.DMChannel]
    prefix: str
    command: commands.Command[Any, ..., Any]
    bot: Trapard

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # OVERWRITE HERE

class GuildContext(Context):
    author: discord.Member
    guild: discord.Guild
    channel: Union[discord.VoiceChannel, discord.TextChannel, discord.Thread]
    me: discord.Member
    prefix: str