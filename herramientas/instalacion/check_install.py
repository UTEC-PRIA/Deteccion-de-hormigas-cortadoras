#!/usr/bin/env python3
import sys
import os
import importlib
import subprocess

def print_status(name, success, error_msg=""):
    if success:
        print(f"✅ {name}: OK")
    else:
        print(f"❌ {name}: FALLO ({error_msg})")

def check_python_module(module_name, display_name=None):
    display = display_name or module_name
    try:
        importlib.import_module(module_name)
        print_status(f"Python Module '{display}'", True)
        return True
    except ImportError as e:
        print_status(f"Python Module '{display}'", False, str(e))
        return False

def check_system_binary(binary_name):
    try:
        subprocess.run(["which", binary_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print_status(f"System Binary '{binary_name}'", True)
        return True
    except subprocess.CalledProcessError:
        print_status(f"System Binary '{binary_name}'", False, "No encontrado en el PATH")
        return False

def main():
    print("===============================================")
    print("🚁 Verificador de Instalación (Health Check)")
    print("===============================================")
    
    all_passed = True
    
    # 1. Dependencias de Python Críticas
    modules = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pymavlink", "PyMAVLink"),
        ("MAVProxy", "MAVProxy"),
        ("future", "Future (MAVProxy dep)"),
        ("open_gopro", "Open GoPro"),
        ("websockets", "WebSockets"),
        ("PIL", "Pillow (Imágenes)"),
    ]
    
    for mod, display in modules:
        if not check_python_module(mod, display):
            all_passed = False
            
    # 2. Binarios del Sistema
    binaries = [
        "mono",
        "nmcli",
        "wine",
        "Xvfb",
        "msiextract"
    ]
    
    for bin_name in binaries:
        if not check_system_binary(bin_name):
            all_passed = False
            
    # 3. Archivos estáticos e Iconos
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    icon_path = os.path.join(project_dir, "app", "static", "ant_icon.png")
    if os.path.exists(icon_path):
        print_status("Ant Icon (static/ant_icon.png)", True)
    else:
        print_status("Ant Icon (static/ant_icon.png)", False, "Archivo no encontrado")
        all_passed = False
        
    print("===============================================")
    if all_passed:
        print("🎉 ¡TODO LISTO! La instalación está 100% saludable.")
        sys.exit(0)
    else:
        print("⚠️ Hubo problemas. Por favor revisa los errores arriba y ejecuta scripts/install.sh nuevamente.")
        sys.exit(1)

if __name__ == "__main__":
    main()
