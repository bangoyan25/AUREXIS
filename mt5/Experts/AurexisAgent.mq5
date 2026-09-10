//+------------------------------------------------------------------+
//|                                                 AurexisAgent.mq5 |
//|                                  Copyright 2026, AUREXIS Systems |
//|                                       https://app.aurexis.web.id |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, AUREXIS Systems"
#property link      "https://app.aurexis.web.id"
#property version   "1.00"
#property strict

#include "../Include/AurexisJson.mqh"
#include "../Include/AurexisWebSocket.mqh"
#include "../Include/AurexisProtocol.mqh"

#define EA_VERSION "1.0.0"

//--- Inputs
input string InpBackendHost   = "app.aurexis.web.id"; // Backend Host
input uint   InpBackendPort   = 443;                   // Backend TLS Port
input string InpAgentId       = "";                    // Agent ID (UUID)
input string InpAgentSecret   = "";                    // Agent Secret Token
input uint   InpHeartbeatSec  = 15;                    // Heartbeat Interval (sec)
input uint   InpReconnectSec  = 5;                     // Reconnect Interval (sec)
input string InpSymbolMap       = "XAUUSD=XAUUSD";       // Broker Symbol Map
input uint   InpTickThrottleMs   = 100;                   // Min Tick Throttle (ms)

//--- Globals
CAurexisWebSocket g_ws;
bool              g_hello_sent = false;
bool              g_is_welcomed = false;
uint              g_last_heartbeat = 0;
MqlTick           g_last_tick;
uint              g_last_tick_send_time = 0;

//+------------------------------------------------------------------+
//| Process incoming server command                                  |
//+------------------------------------------------------------------+
void HandleCommand(CJsonValue *cmd)
{
   if(cmd == NULL) return;

   string cmd_id = cmd.GetString("id");
   string cmd_type = cmd.GetString("command_type");

   Print("[AUREXIS] Command received: ", cmd_type, " [ID: ", cmd_id, "]");

   // 1. Send ACK immediately
   string ack_msg = CAurexisProtocol::FormatAck(cmd_id);
   g_ws.SendText(ack_msg);
   Print("[AUREXIS] Sent ACK for command: ", cmd_id);

   // 2. Execute command
   if(cmd_type == "PING")
   {
      CJsonValue *res = new CJsonValue();
      res.SetType(JSON_OBJECT);
      res.SetBool("pong", true);
      res.SetString("server_time", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
      res.SetNumber("ping_tick", (double)GetTickCount());

      string res_msg = CAurexisProtocol::FormatResult(cmd_id, "COMPLETED", res);
      g_ws.SendText(res_msg);
      Print("[AUREXIS] Completed PING command: ", cmd_id);
   }
   else if(cmd_type == "GET_STATUS")
   {
      CJsonValue *res = new CJsonValue();
      res.SetType(JSON_OBJECT);
      res.SetNumber("login", (double)AccountInfoInteger(ACCOUNT_LOGIN));
      res.SetString("server", AccountInfoString(ACCOUNT_SERVER));
      res.SetString("currency", AccountInfoString(ACCOUNT_CURRENCY));
      res.SetNumber("balance", AccountInfoDouble(ACCOUNT_BALANCE));
      res.SetNumber("equity", AccountInfoDouble(ACCOUNT_EQUITY));
      res.SetNumber("margin", AccountInfoDouble(ACCOUNT_MARGIN));
      res.SetNumber("free_margin", AccountInfoDouble(ACCOUNT_MARGIN_FREE));
      res.SetNumber("terminal_connected", (double)TerminalInfoInteger(TERMINAL_CONNECTED));
      res.SetNumber("trade_allowed", (double)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED));
      res.SetNumber("positions_total", (double)PositionsTotal());
      res.SetNumber("orders_total", (double)OrdersTotal());

      string res_msg = CAurexisProtocol::FormatResult(cmd_id, "COMPLETED", res);
      g_ws.SendText(res_msg);
      Print("[AUREXIS] Completed GET_STATUS command: ", cmd_id);
   }
   else
   {
      Print("[AUREXIS WARNING] Unknown command type: ", cmd_type);
      string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "Unsupported command type: " + cmd_type);
      g_ws.SendText(res_msg);
   }
}

//+------------------------------------------------------------------+
//| WebSocket incoming message callback                              |
//+------------------------------------------------------------------+
void OnWsMessage(const string msg)
{
   CJsonValue *root = CJsonValue::Parse(msg);
   if(root == NULL)
   {
      Print("[AUREXIS ERROR] Failed to parse JSON message: ", msg);
      return;
   }

   string type = root.GetString("type");

   if(type == "welcome")
   {
      g_is_welcomed = true;
      Print("[AUREXIS] Welcome received: ", root.GetString("message"));
   }
   else if(type == "heartbeat_ack")
   {
      Print("[AUREXIS] Heartbeat ACK received from backend.");
   }
   else if(type == "command")
   {
      CJsonValue *cmd = root.Get("command");
      if(cmd != NULL)
         HandleCommand(cmd);
   }
   else if(type == "error")
   {
      Print("[AUREXIS ERROR] Server error [", root.GetString("code"), "]: ", root.GetString("message"));
   }
   else
   {
      Print("[AUREXIS] Unhandled message type: ", type);
   }

   delete root;
}

//+------------------------------------------------------------------+
//| Stream real-time market tick                                     |
//+------------------------------------------------------------------+
void SendMarketTick(bool force = false)
{
   if(!g_ws.IsConnected() || !g_is_welcomed)
      return;

   uint now_tick = GetTickCount();
   if(!force && (now_tick - g_last_tick_send_time < InpTickThrottleMs))
      return;

   MqlTick current_tick;
   if(!SymbolInfoTick(_Symbol, current_tick))
      return;

   // Check if price or time changed (unless force)
   if(!force &&
      current_tick.bid == g_last_tick.bid &&
      current_tick.ask == g_last_tick.ask &&
      current_tick.time == g_last_tick.time)
   {
      return;
   }

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double spread = current_tick.ask - current_tick.bid;

   string msg = CAurexisProtocol::FormatMarketData(
      _Symbol,
      current_tick.bid,
      current_tick.ask,
      spread,
      point,
      digits,
      current_tick.time,
      current_tick.volume
   );

   if(g_ws.SendText(msg))
   {
      g_last_tick = current_tick;
      g_last_tick_send_time = now_tick;
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("=================================================");
   Print(" AUREXIS MT5 Execution Agent v", EA_VERSION, " starting");
   Print(" Build: ", TerminalInfoString(TERMINAL_NAME), " ", IntegerToString(TerminalInfoInteger(TERMINAL_BUILD)));
   Print(" Account: ", AccountInfoInteger(ACCOUNT_LOGIN), " (", AccountInfoString(ACCOUNT_SERVER), ")");
   Print("=================================================");

   if(InpAgentId == "" || InpAgentSecret == "")
   {
      Print("[AUREXIS WARNING] InpAgentId or InpAgentSecret is not set! Please configure EA inputs.");
   }

   string path = "/api/v1/agents/" + InpAgentId + "/ws";
   g_ws.Init(InpBackendHost, InpBackendPort, path, InpAgentSecret);
   g_ws.SetMessageCallback(OnWsMessage);

   EventSetTimer(1);

   if(InpAgentId != "" && InpAgentSecret != "")
   {
      Print("[AUREXIS] Connecting to wss://", InpBackendHost, ":", InpBackendPort, path);
      g_ws.Connect();
   }

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   g_ws.Disconnect();
   Print("[AUREXIS] AurexisAgent stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
{
   g_ws.Tick();

   if(g_ws.IsConnected())
   {
      // Send Hello immediately upon connection
      if(!g_hello_sent)
      {
         string mt5_ver = TerminalInfoString(TERMINAL_NAME) + " " + IntegerToString(TerminalInfoInteger(TERMINAL_BUILD));
         string hello = CAurexisProtocol::FormatHello("1.0.0", mt5_ver, EA_VERSION);
         g_ws.SendText(hello);
         g_hello_sent = true;
         g_last_heartbeat = GetTickCount();
         Print("[AUREXIS] Hello message sent to backend.");
      }
      else
      {
         // Periodic heartbeat
         uint elapsed = (GetTickCount() - g_last_heartbeat) / 1000;
         if(elapsed >= InpHeartbeatSec)
         {
            string mt5_ver = TerminalInfoString(TERMINAL_NAME) + " " + IntegerToString(TerminalInfoInteger(TERMINAL_BUILD));
            string hb = CAurexisProtocol::FormatHeartbeat("CONNECTED", mt5_ver, EA_VERSION);
            g_ws.SendText(hb);
            g_last_heartbeat = GetTickCount();
            Print("[AUREXIS] Sent heartbeat to backend.");
         }

         // Send initial market tick if none sent yet
         if(g_is_welcomed && g_last_tick_send_time == 0)
         {
            SendMarketTick(true);
         }
      }
   }
   else
   {
      g_hello_sent = false;
      g_is_welcomed = false;
      g_last_tick_send_time = 0;
      ZeroMemory(g_last_tick);
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   g_ws.Tick();
   SendMarketTick(false);
}
//+------------------------------------------------------------------+
