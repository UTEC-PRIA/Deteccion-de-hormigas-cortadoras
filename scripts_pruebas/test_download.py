import asyncio
from open_gopro import WiredGoPro
import logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    try:
        gopro = WiredGoPro()
        await gopro.open()
        resp = await gopro.http_command.get_last_captured_media()
        print("Last media:", resp)
        if resp.is_ok:
            media_path = resp.data
            camera_file = f"{media_path.folder}/{media_path.file}"
            print("Camera file:", camera_file)
            
            # Let's try to get the media list to see if the URL is different
            print("Base URL:", gopro._base_url)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
