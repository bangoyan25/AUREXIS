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
#include <Trade\Trade.mqh>

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
CTrade            g_trade;
bool              g_hello_sent = false;
bool              g_is_welcomed = false;
uint              g_last_heartbeat = 0;
MqlTick           g_last_tick;
uint              g_last_tick_send_time = 0;

//+------------------------------------------------------------------+
//| Check if account is DEMO                                         |
//+------------------------------------------------------------------+
bool IsDemoAccount()
{
   long trade_mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   string srv = AccountInfoString(ACCOUNT_SERVER);
   string srv_lower = srv;
   StringToLower(srv_lower);
   return (trade_mode == ACCOUNT_TRADE_MODE_DEMO) || (StringFind(srv_lower, "demo") >= 0);
}

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
      res.SetNumber("trade_mode", (double)AccountInfoInteger(ACCOUNT_TRADE_MODE));
      res.SetBool("is_demo", IsDemoAccount());
      res.SetNumber("positions_total", (double)PositionsTotal());
      res.SetNumber("orders_total", (double)OrdersTotal());

      string res_msg = CAurexisProtocol::FormatResult(cmd_id, "COMPLETED", res);
      g_ws.SendText(res_msg);
      Print("[AUREXIS] Completed GET_STATUS command: ", cmd_id);
   }
   else if(cmd_type == "OPEN_POSITION")
   {
      if(TerminalInfoInteger(TERMINAL_CONNECTED) != 1)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "TERMINAL_DISCONNECTED");
         g_ws.SendText(res_msg);
         return;
      }
      if(AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) != 1)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "TRADE_NOT_ALLOWED");
         g_ws.SendText(res_msg);
         return;
      }
      if(!IsDemoAccount())
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "REJECTED_NOT_DEMO: Phase 4A strictly restricted to DEMO accounts");
         g_ws.SendText(res_msg);
         return;
      }

      CJsonValue *payload = cmd.Get("payload");
      if(payload == NULL)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "MISSING_PAYLOAD");
         g_ws.SendText(res_msg);
         return;
      }

      string sym = payload.GetString("symbol", "XAUUSD");
      string side = payload.GetString("side", "");
      double vol = payload.GetDouble("volume", 0.01);
      string client_order_id = payload.GetString("client_order_id", "");
      double sl = payload.GetDouble("stop_loss", 0.0);
      double tp = payload.GetDouble("take_profit", 0.0);
      ulong dev = (ulong)payload.GetLong("deviation", 20);
      string comment = payload.GetString("comment", "AUREXIS_DEMO");

      if(sym != "XAUUSD")
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "INVALID_SYMBOL: Only XAUUSD permitted");
         g_ws.SendText(res_msg);
         return;
      }
      if(side != "BUY" && side != "SELL")
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "INVALID_SIDE: side must be BUY or SELL");
         g_ws.SendText(res_msg);
         return;
      }
      if(!SymbolSelect(sym, true))
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "SYMBOL_UNAVAILABLE: " + sym);
         g_ws.SendText(res_msg);
         return;
      }

      ENUM_SYMBOL_TRADE_MODE sym_mode = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(sym, SYMBOL_TRADE_MODE);
      if(sym_mode != SYMBOL_TRADE_MODE_FULL)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "TRADE_MODE_DISABLED");
         g_ws.SendText(res_msg);
         return;
      }

      double min_vol = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
      double max_vol = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
      if(vol < min_vol || vol > max_vol)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, 
            StringFormat("INVALID_VOLUME: volume %.2f outside [%.2f, %.2f]", vol, min_vol, max_vol));
         g_ws.SendText(res_msg);
         return;
      }

      g_trade.SetDeviationInPoints(dev > 0 ? dev : 20);
      g_trade.SetTypeFillingBySymbol(sym);

      bool trade_ok = false;
      if(side == "BUY")
         trade_ok = g_trade.Buy(vol, sym, 0.0, sl, tp, comment);
      else if(side == "SELL")
         trade_ok = g_trade.Sell(vol, sym, 0.0, sl, tp, comment);

      uint retcode = g_trade.ResultRetcode();
      ulong deal = g_trade.ResultDeal();
      ulong order = g_trade.ResultOrder();
      double exec_vol = g_trade.ResultVolume();
      double exec_price = g_trade.ResultPrice();

      if(trade_ok && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_PLACED))
      {
         ulong pos_ticket = deal;
         if(pos_ticket == 0) pos_ticket = order;
         for(int p = PositionsTotal() - 1; p >= 0; p--)
         {
            ulong t = PositionGetTicket(p);
            if(t > 0 && PositionGetString(POSITION_SYMBOL) == sym)
            {
               pos_ticket = t;
               break;
            }
         }

         CJsonValue *res = new CJsonValue();
         res.SetType(JSON_OBJECT);
         res.SetString("command_id", cmd_id);
         res.SetString("client_order_id", client_order_id);
         res.SetBool("success", true);
         res.SetNumber("retcode", (double)retcode);
         res.SetString("retcode_description", g_trade.ResultRetcodeDescription());
         res.SetNumber("order_ticket", (double)order);
         res.SetNumber("deal_ticket", (double)deal);
         res.SetNumber("position_ticket", (double)pos_ticket);
         res.SetNumber("executed_volume", exec_vol > 0 ? exec_vol : vol);
         res.SetNumber("executed_price", exec_price);
         res.SetString("symbol", sym);
         res.SetString("side", side);
         res.SetString("timestamp", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));

         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "COMPLETED", res);
         g_ws.SendText(res_msg);
         Print("[AUREXIS] Completed OPEN_POSITION: cmd=", cmd_id, " ticket=", pos_ticket, " price=", exec_price);
      }
      else
      {
         string err = StringFormat("TRADE_REJECTED: retcode %d (%s)", retcode, g_trade.ResultRetcodeDescription());
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, err);
         g_ws.SendText(res_msg);
         Print("[AUREXIS ERROR] OPEN_POSITION failed: ", err);
      }
   }
   else if(cmd_type == "CLOSE_POSITION")
   {
      if(TerminalInfoInteger(TERMINAL_CONNECTED) != 1)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "TERMINAL_DISCONNECTED");
         g_ws.SendText(res_msg);
         return;
      }
      if(AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) != 1)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "TRADE_NOT_ALLOWED");
         g_ws.SendText(res_msg);
         return;
      }
      if(!IsDemoAccount())
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "REJECTED_NOT_DEMO");
         g_ws.SendText(res_msg);
         return;
      }

      CJsonValue *payload = cmd.Get("payload");
      if(payload == NULL)
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, "MISSING_PAYLOAD");
         g_ws.SendText(res_msg);
         return;
      }

      ulong pos_ticket = (ulong)payload.GetLong("position_ticket", 0);
      string client_order_id = payload.GetString("client_order_id", "");
      ulong dev = (ulong)payload.GetLong("deviation", 20);

      if(pos_ticket == 0 && PositionsTotal() == 1)
      {
         pos_ticket = PositionGetTicket(0);
      }

      if(pos_ticket == 0 || !PositionSelectByTicket(pos_ticket))
      {
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, 
            StringFormat("POSITION_NOT_FOUND: ticket %I64u not found or already closed", pos_ticket));
         g_ws.SendText(res_msg);
         return;
      }

      string pos_symbol = PositionGetString(POSITION_SYMBOL);
      g_trade.SetDeviationInPoints(dev > 0 ? dev : 20);
      g_trade.SetTypeFillingBySymbol(pos_symbol);

      bool close_res = g_trade.PositionClose(pos_ticket);
      uint retcode = g_trade.ResultRetcode();
      ulong deal = g_trade.ResultDeal();
      ulong order = g_trade.ResultOrder();
      double exec_vol = g_trade.ResultVolume();
      double exec_price = g_trade.ResultPrice();

      if(close_res && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_PLACED))
      {
         CJsonValue *res = new CJsonValue();
         res.SetType(JSON_OBJECT);
         res.SetString("command_id", cmd_id);
         res.SetString("client_order_id", client_order_id);
         res.SetBool("success", true);
         res.SetNumber("retcode", (double)retcode);
         res.SetString("retcode_description", g_trade.ResultRetcodeDescription());
         res.SetNumber("order_ticket", (double)order);
         res.SetNumber("deal_ticket", (double)deal);
         res.SetNumber("position_ticket", (double)pos_ticket);
         res.SetNumber("executed_volume", exec_vol);
         res.SetNumber("executed_price", exec_price);
         res.SetString("symbol", pos_symbol);
         res.SetString("timestamp", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));

         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "COMPLETED", res);
         g_ws.SendText(res_msg);
         Print("[AUREXIS] Completed CLOSE_POSITION: cmd=", cmd_id, " ticket=", pos_ticket, " price=", exec_price);
      }
      else
      {
         string err = StringFormat("CLOSE_REJECTED: retcode %d (%s)", retcode, g_trade.ResultRetcodeDescription());
         string res_msg = CAurexisProtocol::FormatResult(cmd_id, "FAILED", NULL, err);
         g_ws.SendText(res_msg);
         Print("[AUREXIS ERROR] CLOSE_POSITION failed: ", err);
      }
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

   g_trade.SetExpertMagicNumber(1001);
   g_trade.SetMarginMode();

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
