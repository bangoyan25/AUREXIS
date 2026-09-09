@echo off
:: ==============================================================================
:: Disconnect RDP session and transfer to console
:: Keeps GUI active for MT5 EA continuous execution without RDP suspension
:: ==============================================================================

echo Transferring RDP session to console...
for /f "tokens=3" %%a in ('query session ^| findstr /i ">"') do set RDP_SESSION_ID=%%a

if defined RDP_SESSION_ID (
    echo Active RDP session ID: %RDP_SESSION_ID%
    %windir%\System32\tscon.exe %RDP_SESSION_ID% /dest:console
) else (
    echo Could not determine session ID from query session. Attempting sessionname...
    %windir%\System32\tscon.exe %sessionname% /dest:console
)

if %errorlevel% neq 0 (
    echo Note: tscon may require elevated administrator privileges.
    pause
)
