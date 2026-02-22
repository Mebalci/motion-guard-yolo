# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Proje kökü: build klasörünün bir üstü
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR      = os.path.join(PROJECT_ROOT, "src")
ASSETS_DIR   = os.path.join(PROJECT_ROOT, "assets")
HOOKS_DIR    = os.path.join(PROJECT_ROOT, "hooks")

# Paketleri topla
torch_datas, torch_binaries, torch_hiddenimports = collect_all("torch")
torchvision_datas, torchvision_binaries, torchvision_hiddenimports = collect_all("torchvision")
ultralytics_datas, ultralytics_binaries, ultralytics_hiddenimports = collect_all("ultralytics")

# Torch lib DLL'leri
import torch as _torch
_torch_lib = os.path.join(os.path.dirname(_torch.__file__), "lib")
torch_dll_binaries = []
if os.path.isdir(_torch_lib):
    for f in os.listdir(_torch_lib):
        if f.lower().endswith(".dll"):
            torch_dll_binaries.append((os.path.join(_torch_lib, f), "torch/lib"))
print(f"[SPEC] Torch DLL sayisi: {len(torch_dll_binaries)}")

a = Analysis(
    [os.path.join(SRC_DIR, "main.py")],
    pathex=[PROJECT_ROOT, SRC_DIR],
    binaries=torch_binaries + torchvision_binaries + ultralytics_binaries + torch_dll_binaries,
    datas=[
        # assets -> dist içinde assets/ olarak kalsın
        (os.path.join(ASSETS_DIR, "yolov8n.pt"), "assets"),
        (os.path.join(ASSETS_DIR, "Mebalci.png"), "assets"),
        (os.path.join(ASSETS_DIR, "Mebalci.ico"), "assets"),
        (os.path.join(ASSETS_DIR, "dilili.mp3"), "assets"),

        *torch_datas,
        *torchvision_datas,
        *ultralytics_datas,
    ],
    hiddenimports=list(set(
        torch_hiddenimports
        + torchvision_hiddenimports
        + ultralytics_hiddenimports
        + [
            "PIL",
            "PIL.Image",
            "cv2",
            "pygame",
            "pygame.mixer",
            "customtkinter",
            "tkinter",
            "numpy",
            "yaml",
            "packaging",
        ]
    )),
    hookspath=[HOOKS_DIR],
    runtime_hooks=[os.path.join(HOOKS_DIR, "rthook_torch.py")],
    excludes=["matplotlib", "notebook", "IPython", "sklearn"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MotionGuard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ASSETS_DIR, "Mebalci.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MotionGuard",
)