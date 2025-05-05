@echo off
setlocal enabledelayedexpansion

:: Set paths
set "FFPROBE=ffprobe"
set "FILE1=D:\TV Shows\Last Man Standing (2011)\Season 5\New folder\Last Man Standing (2011) - S05E02 - Free Range Parents WEBDL-1080p.mkv"
set "FILE2=D:\TV Shows\Saturday Night Live (1975)\Season 50\Saturday Night Live - S50E19 - Quinta Brunson + Benson Boone WEBDL-1080p.mkv"

echo ===================== FILE 1: S05E02 =====================
%FFPROBE% -hide_banner -loglevel info -show_format -show_streams "!FILE1!"
echo.

echo ===================== FILE 2: SNL S50E19 =====================
%FFPROBE% -hide_banner -loglevel info -show_format -show_streams "!FILE2!"
echo.

pause
