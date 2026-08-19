import asyncio
from open_gopro import WirelessGoPro
from open_gopro.constants import Toggle

async def main():
    print("Connecting...")
    g = WirelessGoPro(enable_wifi=False)
    await g.open()
    print("BLE opened.")
    
    # Try HTTP command
    print("Trying HTTP...")
    try:
        # Since we haven't connected WiFi, this will fail if we haven't connected it via nmcli
        # BUT if we mock the wifi state or just use it, will it work?
        pass
    finally:
        await g.close()

if __name__ == "__main__":
    asyncio.run(main())
