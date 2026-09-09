# AUREXIS MT5 Execution Agent

Native MetaTrader 5 execution agent connecting to the AUREXIS backend over secure WebSocket (`wss://`).

## Architecture

- **`mt5/Experts/AurexisAgent.mq5`**: Main Expert Advisor execution loop, lifecycle handlers (`OnInit`, `OnDeinit`, `OnTimer`, `OnTick`), command execution (`PING`, `GET_STATUS`).
- **`mt5/Include/AurexisWebSocket.mqh`**: Pure MQL5 RFC 6455 WebSocket client using MT5 native TLS socket API (`SocketCreate`, `SocketConnect`, `SocketTlsHandshake`, `SocketSend`, `SocketRead`). No external DLLs required.
- **`mt5/Include/AurexisProtocol.mqh`**: Wire protocol serialization and deserialization adhering to `backend/ws/agent_protocol.py` (`hello`, `heartbeat`, `ack`, `result`).
- **`mt5/Include/AurexisJson.mqh`**: Zero-dependency MQL5 JSON parser and serializer.
- **`mt5/Presets/default.set`**: Template EA input parameter set file.

## Requirements

- MetaTrader 5 Build 4755+ (Build 6157 verified).
- Windows Server 2019 / Windows 10/11 x64.
- TLS 1.2+ network access to `app.aurexis.web.id:443`.

## Deployment & Setup

Run the provisioning script from an elevated PowerShell console:

```powershell
.\scripts\windows\setup_mt5_agent.ps1 -AgentId "<AGENT_UUID>" -AgentSecret "<SECRET_TOKEN>"
```

The script:
1. Copies all includes, EA source files, binaries, and presets to MT5's roaming data folder.
2. Configures `common.ini` to enable WebRequest permissions and AutoTrading.
3. Sets Windows Server 2019 Terminal Services session timeout to 0 (Never disconnect/terminate).

## RDP Session Resilience

When disconnecting from the Windows Server 2019 VPS, do NOT close the RDP window directly.
Instead, run:

```cmd
scripts\windows\disconnect_rdp.bat
```

This invokes `tscon %sessionname% /dest:console` to transfer the active user session directly to the physical console, keeping GUI message loops and MT5 execution active.

