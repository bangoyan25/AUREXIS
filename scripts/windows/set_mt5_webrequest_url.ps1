<#
.SYNOPSIS
    Automates adding the backend URL to MetaTrader 5 WebRequest allowlist.
.DESCRIPTION
    MetaTrader 5 encrypts the WebRequestUrl entry in common.ini using an internal algorithm.
    Writing plaintext to common.ini corrupts MT5's URL allowlist and results in MQL5 runtime
    error 4014 (ERR_FUNCTION_NOT_ALLOWED).
    This script automates MT5 Options GUI to safely add https://app.aurexis.web.id and save it.
#>

param (
    [string]$Url = "https://app.aurexis.web.id"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

$proc = Get-Process terminal64 -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Host "Starting MT5 terminal..."
    Start-Process "C:\Program Files\MetaTrader 5\terminal64.exe"
    Start-Sleep -Seconds 5
    $proc = Get-Process terminal64 -ErrorAction Stop
}

# Ensure window handle is present
$retries = 10
while ($proc.MainWindowHandle -eq 0 -and $retries -gt 0) {
    Start-Sleep -Seconds 1
    $proc.Refresh()
    $retries--
}

if ($proc.MainWindowHandle -eq 0) {
    throw "MT5 terminal window handle not found. Please ensure MT5 is running on the active desktop session."
}

# Open Options dialog (Ctrl+O)
[System.Windows.Forms.SendKeys]::SendWait("^o")
Start-Sleep -Milliseconds 800

$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
$optWindow = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "Options")))

if (-not $optWindow) {
    throw "Options dialog failed to open."
}

Write-Host "Options dialog opened."

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class MT5Win32 {
    [DllImport("user32.dll")]
    public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, string lParam);
    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
    public const uint MOUSEEVENTF_LEFTDOWN = 0x02;
    public const uint MOUSEEVENTF_LEFTUP = 0x04;
    public static void DoubleClick(int x, int y) {
        SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
        System.Threading.Thread.Sleep(50);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
    }
}
"@

# 1. Check Allow WebRequest checkbox (Id: 10322)
$chk = $optWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, "10322")))
if ($chk) {
    $chkHandle = $chk.Current.NativeWindowHandle
    $isChecked = [MT5Win32]::SendMessage([IntPtr]$chkHandle, 0x00F0, [IntPtr]::Zero, [IntPtr]::Zero) # BM_GETCHECK
    if ($isChecked -ne 1) {
        [MT5Win32]::SendMessage([IntPtr]$chkHandle, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) # BM_CLICK
        Write-Host "Enabled 'Allow WebRequest for listed URL:' checkbox."
    }
}

# 2. Add URL in SysListView32 (Id: 10191)
$list = $optWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, "10191")))
if ($list) {
    $listHandle = $list.Current.NativeWindowHandle
    $rect = $list.Current.BoundingRectangle

    # Double click first entry
    $clickX = [int]($rect.X + 30)
    $clickY = [int]($rect.Y + 12)
    [MT5Win32]::DoubleClick($clickX, $clickY)
    Start-Sleep -Milliseconds 400

    # Look for popup edit control
    $edit = $optWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, "Edit")))
    if ($edit) {
        $editHandle = $edit.Current.NativeWindowHandle
        [MT5Win32]::SendMessage([IntPtr]$editHandle, 0x000C, [IntPtr]::Zero, $Url) # WM_SETTEXT
        Start-Sleep -Milliseconds 100
        [MT5Win32]::PostMessage([IntPtr]$editHandle, 0x0100, [IntPtr]0x0D, [IntPtr]0x001C0001) # WM_KEYDOWN RETURN
        [MT5Win32]::PostMessage([IntPtr]$editHandle, 0x0101, [IntPtr]0x0D, [IntPtr]0xC01C0001) # WM_KEYUP RETURN
        Start-Sleep -Milliseconds 300
        Write-Host "Entered URL: $Url"
    }
}

# 3. Click OK button (Id: 1)
$btnOk = $optWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, "1")))
if ($btnOk) {
    $btnOkHandle = $btnOk.Current.NativeWindowHandle
    [MT5Win32]::SendMessage([IntPtr]$btnOkHandle, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) # BM_CLICK
    Start-Sleep -Milliseconds 500
    Write-Host "Options saved successfully."
}
