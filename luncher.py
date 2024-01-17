from bot import Trapard
import asyncio, os

async def run_bot():
    async with Trapard() as bot:
        await bot.start(os.environ.get("TRAPARD_DEV_TOKEN"))
    
async def main():
    """Launches the bot."""
    await run_bot()

if __name__ == '__main__':
    asyncio.run(main())