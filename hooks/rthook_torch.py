# hooks/rthook_torch.py
import os
import sys
import inspect

if getattr(sys, "frozen", False):
    base = sys._MEIPASS

    # DLL yollarını ekle
    candidates = [
        base,
        os.path.join(base, "torch", "lib"),
        os.path.dirname(base),
    ]
    for path in candidates:
        if os.path.isdir(path):
            os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(path)
            except Exception:
                pass

    # inspect.getsource frozen ortamda çalışmaz — monkey-patch
    _original_getsource = inspect.getsource

    def _safe_getsource(obj):
        try:
            return _original_getsource(obj)
        except (OSError, TypeError):
            return ""

    inspect.getsource = _safe_getsource

    _original_getsourcelines = inspect.getsourcelines

    def _safe_getsourcelines(obj):
        try:
            return _original_getsourcelines(obj)
        except (OSError, TypeError):
            return ([], 0)

    inspect.getsourcelines = _safe_getsourcelines