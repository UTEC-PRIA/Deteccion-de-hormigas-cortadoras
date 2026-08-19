import asyncio
from open_gopro import WiredGoPro

async def main():
    async with WiredGoPro() as gopro:
        print("Connected via USB!")
        # Print all HTTP commands available
        commands = dir(gopro.http_command)
        print("HTTP Commands related to AP/WiFi/Bluetooth:")
        for cmd in commands:
            if 'ap' in cmd.lower() or 'wifi' in cmd.lower() or 'ble' in cmd.lower() or 'wireless' in cmd.lower():
                print(f" - {cmd}")
        
        # Print all HTTP settings
        settings = dir(gopro.http_setting)
        print("HTTP Settings related to AP/WiFi:")
        for s in settings:
            if 'ap' in s.lower() or 'wifi' in s.lower() or 'wireless' in s.lower():
                print(f" - {s}")
                
        # Also let's try to get the AP SSID and password if possible
        try:
            res = await gopro.http_command.get_wifi_ssid()
            print("SSID:", res)
        except Exception as e:
            pass

asyncio.run(main())
