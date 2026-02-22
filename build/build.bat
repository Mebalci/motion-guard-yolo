@echo off
setlocal

REM build.bat - Motion Guard Build Script
REM Bu dosyayı build\ klasörü içinde çalıştır

echo ========================================
echo   Motion Guard - Build Basliyor...
echo ========================================

cd /d "%~dp0\.."
set ROOT=%cd%

echo Proje Koku: %ROOT%

echo [1/3] Eski build dosyalari temizleniyor...
if exist "%ROOT%\dist\MotionGuard" rmdir /s /q "%ROOT%\dist\MotionGuard"
if exist "%ROOT%\build\MotionGuard" rmdir /s /q "%ROOT%\build\MotionGuard"

echo [2/3] PyInstaller build aliniyor...
pyinstaller "%ROOT%\build\main.spec" --clean --noconfirm

echo [3/3] Visual C++ Runtime DLL kontrol ediliyor...
set DIST_DIR=%ROOT%\dist\MotionGuard
set SYS32=C:\Windows\System32

for %%f in (msvcp140.dll vcruntime140.dll vcruntime140_1.dll) do (
    if not exist "%DIST_DIR%\%%f" (
        if exist "%SYS32%\%%f" (
            copy "%SYS32%\%%f" "%DIST_DIR%\%%f" >nul
            echo   Kopyalandi: %%f
        ) else (
            echo   UYARI: %%f bulunamadi - Visual C++ Redistributable yuklu olmayabilir!
        )
    ) else (
        echo   Mevcut: %%f
    )
)

echo.
echo ========================================
echo   Build TAMAMLANDI!
echo   Konum: dist\MotionGuard\MotionGuard.exe
echo ========================================
pause
endlocal