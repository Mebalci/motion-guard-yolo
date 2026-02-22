# hooks/hook-torch.py
# PyInstaller'ın atlayabileceği Torch DLL'lerini zorla ekler

import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

binaries = collect_dynamic_libs('torch')
datas    = collect_data_files('torch')

# torch/lib içindeki tüm DLL'leri manuel tara
try:
    import torch
    torch_lib_path = os.path.join(os.path.dirname(torch.__file__), 'lib')
    if os.path.exists(torch_lib_path):
        for fname in os.listdir(torch_lib_path):
            if fname.endswith('.dll'):
                full = os.path.join(torch_lib_path, fname)
                binaries.append((full, 'torch/lib'))
        print(f"[hook-torch] {torch_lib_path} klasöründen DLL'ler eklendi.")
    else:
        print("[hook-torch] torch/lib klasörü bulunamadı!")
except Exception as e:
    print(f"[hook-torch] Hata: {e}")
