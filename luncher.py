from bot import Trapard
from Cogs.utils.functions import getVar
import asyncio, os, colorama

async def run_bot():
    async with Trapard() as bot:
        await bot.start(getVar('TRAPARD_TOKEN'))
    
async def main():
    """Launches the bot."""
    await run_bot()

if __name__ == '__main__':
    asyncio.run(main())