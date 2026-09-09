//+------------------------------------------------------------------+
//|                                             AurexisProtocol.mqh  |
//|                                  Copyright 2026, AUREXIS Systems |
//|                                       https://app.aurexis.web.id |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, AUREXIS Systems"
#property link      "https://app.aurexis.web.id"
#property strict

#include "AurexisJson.mqh"

struct SIncomingCommand
{
   string   id;
   string   command_type;
   string   payload_json;
};

class CAurexisProtocol
{
public:
   static string FormatHello(string agent_ver, string mt5_ver, string ea_ver)
   {
      CJsonValue root;
      root.SetType(JSON_OBJECT);
      root.SetString("type", "hello");
      root.SetString("agent_version", agent_ver);
      root.SetString("mt5_version", mt5_ver);
      root.SetString("ea_version", ea_ver);

      CJsonValue *caps = new CJsonValue();
      caps.SetType(JSON_ARRAY);
      CJsonValue *cap1 = new CJsonValue(); cap1.SetString("PING"); caps.Add(cap1);
      CJsonValue *cap2 = new CJsonValue(); cap2.SetString("GET_STATUS"); caps.Add(cap2);
      root.Set("capabilities", caps);

      return root.Serialize();
   }

   static string FormatHeartbeat(string status, string mt5_ver, string ea_ver)
   {
      CJsonValue root;
      root.SetType(JSON_OBJECT);
      root.SetString("type", "heartbeat");
      root.SetString("status", status);
      root.SetString("mt5_version", mt5_ver);
      root.SetString("ea_version", ea_ver);
      return root.Serialize();
   }

   static string FormatAck(string command_id)
   {
      CJsonValue root;
      root.SetType(JSON_OBJECT);
      root.SetString("type", "ack");
      root.SetString("command_id", command_id);
      return root.Serialize();
   }

   static string FormatResult(string command_id, string status, CJsonValue *result_val, string error_msg = "")
   {
      CJsonValue root;
      root.SetType(JSON_OBJECT);
      root.SetString("type", "result");
      root.SetString("command_id", command_id);
      root.SetString("status", status);
      if(result_val != NULL)
         root.Set("result", result_val);
      else
         root.SetNull("result");

      if(error_msg != "")
         root.SetString("error_message", error_msg);
      else
         root.SetNull("error_message");

      return root.Serialize();
   }
};
//+------------------------------------------------------------------+
