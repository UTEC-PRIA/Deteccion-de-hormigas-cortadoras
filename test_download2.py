import asyncio
from open_gopro import WiredGoPro
import logging
logging.basicConfig(level=logging.WARNING)

async def main():
    try:
        gopro = WiredGoPro()
        await gopro.open()
        print("Getting media list...")
        resp = await gopro.http_command.get_media_list()
        if resp.is_ok:
            media_list = resp.data.files
            if media_list:
                # Get the last item. Wait, media_list is a flat list?
                print(f"Total files: {len(media_list)}")
                last_media = media_list[-1]
                print(f"Last media object: {last_media}")
                print(f"Last media name: {last_media.filename}")
            else:
                print("No files found.")
        else:
            print("Failed to get media list")
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
