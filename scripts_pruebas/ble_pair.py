import asyncio
from open_gopro import WirelessGoPro
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    print("Iniciando busqueda BLE para GoPro...")
    try:
        # Will search and connect to the first GoPro it finds via BLE
        async with WirelessGoPro() as gopro:
            print("¡Conectado por BLE y WiFi!")
            
            # Save the WiFi details
            print("Guardando configuracion...")
            ssid = await gopro.ble_command.get_wifi_ssid()
            password = await gopro.ble_command.get_wifi_password()
            
            print(f"SSID: {ssid.data}")
            print(f"Password: {password.data}")
            
            # Write to a file so we can configure NetworkManager
            with open("/tmp/gopro_wifi.txt", "w") as f:
                f.write(f"{ssid.data}\n{password.data}\n")
                
    except Exception as e:
        print(f"Error conectando por BLE: {e}")

if __name__ == "__main__":
    asyncio.run(main())
