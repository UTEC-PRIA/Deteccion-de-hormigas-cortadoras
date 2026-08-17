import asyncio
from open_gopro import WiredGoPro
import json

async def main():
    async with WiredGoPro() as gopro:
        print("GoPro conectada por USB.")
        
        print("Obteniendo SSID...")
        try:
            ssid_resp = await gopro.http_command.get_wifi_ssid()
            print("SSID Respuesta:", ssid_resp.data)
        except Exception as e:
            print("Error SSID:", e)
            
        print("Obteniendo Password...")
        try:
            pass_resp = await gopro.http_command.get_wifi_password()
            print("Password Respuesta:", pass_resp.data)
        except Exception as e:
            print("Error Password:", e)
            
        print("Activando WiFi (AP)...")
        try:
            # Depending on OpenGoPro version, the toggle might be different, let's try standard
            from open_gopro.constants import Toggle
            ap_resp = await gopro.http_command.set_ap_state(state=Toggle.ENABLE)
            print("AP Activado:", ap_resp.is_ok)
        except Exception as e:
            print("Error activando AP:", e)
            
        print("Hecho.")

if __name__ == "__main__":
    asyncio.run(main())
