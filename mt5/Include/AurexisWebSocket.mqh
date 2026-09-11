//+------------------------------------------------------------------+
//|                                             AurexisWebSocket.mqh |
//|                                  Copyright 2026, AUREXIS Systems |
//|                                       https://app.aurexis.web.id |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, AUREXIS Systems"
#property link      "https://app.aurexis.web.id"
#property strict

enum ENUM_WS_STATE
{
   WS_STATE_DISCONNECTED,
   WS_STATE_CONNECTING,
   WS_STATE_TLS_HANDSHAKE,
   WS_STATE_WS_HANDSHAKE,
   WS_STATE_CONNECTED,
   WS_STATE_READY
};

enum ENUM_WS_OPCODE
{
   WS_OP_CONTINUATION = 0x0,
   WS_OP_TEXT         = 0x1,
   WS_OP_BINARY       = 0x2,
   WS_OP_CLOSE        = 0x8,
   WS_OP_PING         = 0x9,
   WS_OP_PONG         = 0xA
};

typedef void (*WsMessageCallback)(const string message);

class CAurexisWebSocket
{
private:
   int               m_socket;
   string            m_host;
   uint              m_port;
   string            m_path;
   string            m_token;
   ENUM_WS_STATE     m_state;
   uint              m_last_connect_time;
   uint              m_reconnect_delay;
   string            m_sec_ws_key;

   bool              m_is_tls;
   uchar             m_rx_buf[];
   int               m_rx_len;

   WsMessageCallback m_on_message;

   string GenerateSecKey()
   {
      uchar nonce[16];
      for(int i = 0; i < 16; i++)
         nonce[i] = (uchar)(MathRand() & 0xFF);
      uchar empty_key[], b64[];
      CryptEncode(CRYPT_BASE64, nonce, empty_key, b64);
      return CharArrayToString(b64);
   }

   bool SendHttpUpgrade()
   {
      m_sec_ws_key = GenerateSecKey();
      string req = "GET " + m_path + " HTTP/1.1\r\n";
      req += "Host: " + m_host + "\r\n";
      req += "Upgrade: websocket\r\n";
      req += "Connection: Upgrade\r\n";
      req += "Sec-WebSocket-Key: " + m_sec_ws_key + "\r\n";
      req += "Sec-WebSocket-Version: 13\r\n";
      if(m_token != "")
         req += "Authorization: Bearer " + m_token + "\r\n";
      req += "\r\n";

      uchar req_bytes[];
      StringToCharArray(req, req_bytes);
      int to_send = ArraySize(req_bytes) - 1;
      int sent = m_is_tls ? SocketTlsSend(m_socket, req_bytes, to_send) : SocketSend(m_socket, req_bytes, to_send);
      return (sent == to_send);
   }

   bool SendFrame(ENUM_WS_OPCODE opcode, const uchar &payload[], int payload_len)
   {
      if(m_socket == INVALID_HANDLE || !SocketIsConnected(m_socket))
         return false;

      int hdr_len = 2;
      if(payload_len <= 125)
         hdr_len += 4;
      else if(payload_len <= 65535)
         hdr_len += 6;
      else
         hdr_len += 12;

      uchar frame[];
      ArrayResize(frame, hdr_len + payload_len);

      frame[0] = (uchar)(0x80 | (opcode & 0x0F));

      uchar mask[4];
      for(int i = 0; i < 4; i++)
         mask[i] = (uchar)(MathRand() & 0xFF);

      int pos = 1;
      if(payload_len <= 125)
      {
         frame[pos++] = (uchar)(0x80 | (payload_len & 0x7F));
      }
      else if(payload_len <= 65535)
      {
         frame[pos++] = (uchar)(0x80 | 126);
         frame[pos++] = (uchar)((payload_len >> 8) & 0xFF);
         frame[pos++] = (uchar)(payload_len & 0xFF);
      }
      else
      {
         frame[pos++] = (uchar)(0x80 | 127);
         for(int i = 7; i >= 0; i--)
            frame[pos++] = (uchar)((((ulong)payload_len) >> (i * 8)) & 0xFF);
      }

      for(int i = 0; i < 4; i++)
         frame[pos++] = mask[i];

      for(int i = 0; i < payload_len; i++)
         frame[pos + i] = (uchar)(payload[i] ^ mask[i % 4]);

      int total_len = hdr_len + payload_len;
      int sent_total = 0;
      int attempts = 0;
      while(sent_total < total_len && attempts < 100)
      {
         uchar slice[];
         int to_send = total_len - sent_total;
         ArrayCopy(slice, frame, 0, sent_total, to_send);
         int sent = m_is_tls ? SocketTlsSend(m_socket, slice, to_send) : SocketSend(m_socket, slice, to_send);
         if(sent <= 0)
         {
            Print("[AUREXIS WS ERROR] Socket send failed. Error: ", GetLastError());
            return false;
         }
         sent_total += sent;
         attempts++;
      }
      return (sent_total == total_len);
   }

   void ProcessHttpUpgradeResponse()
   {
      string resp = CharArrayToString(m_rx_buf, 0, m_rx_len);
      int header_end = StringFind(resp, "\r\n\r\n");
      if(header_end < 0)
         return;

      if(StringFind(resp, "101") >= 0 && (StringFind(resp, "Switching Protocols") >= 0 || StringFind(resp, "Upgrade") >= 0))
      {
         Print("[AUREXIS WS] Handshake success. Switching Protocols 101.");
         m_state = WS_STATE_CONNECTED;
         int bytes_to_discard = header_end + 4;
         int rem = m_rx_len - bytes_to_discard;
         if(rem > 0)
         {
            ArrayCopy(m_rx_buf, m_rx_buf, 0, bytes_to_discard, rem);
            m_rx_len = rem;
         }
         else
         {
            m_rx_len = 0;
            ArrayResize(m_rx_buf, 0);
         }
      }
      else
      {
         Print("[AUREXIS WS] Handshake failed. Response:\n", resp);
         Disconnect();
      }
   }

   void ProcessFrames()
   {
      while(m_rx_len >= 2)
      {
         uchar b0 = m_rx_buf[0];
         uchar b1 = m_rx_buf[1];
         bool fin = ((b0 & 0x80) != 0);
         ENUM_WS_OPCODE opcode = (ENUM_WS_OPCODE)(b0 & 0x0F);
         bool has_mask = ((b1 & 0x80) != 0);
         ulong payload_len = (ulong)(b1 & 0x7F);

         int hdr_len = 2;
         if(payload_len == 126)
         {
            if(m_rx_len < 4) return;
            payload_len = ((ulong)m_rx_buf[2] << 8) | (ulong)m_rx_buf[3];
            hdr_len = 4;
         }
         else if(payload_len == 127)
         {
            if(m_rx_len < 10) return;
            payload_len = 0;
            for(int i = 0; i < 8; i++)
               payload_len = (payload_len << 8) | (ulong)m_rx_buf[2 + i];
            hdr_len = 10;
         }

         uchar mask[4];
         if(has_mask)
         {
            if(m_rx_len < hdr_len + 4) return;
            for(int i = 0; i < 4; i++)
               mask[i] = m_rx_buf[hdr_len + i];
            hdr_len += 4;
         }

         if((ulong)m_rx_len < (ulong)hdr_len + payload_len)
            return;

         int plen = (int)payload_len;
         uchar payload[];
         ArrayResize(payload, plen);
         for(int i = 0; i < plen; i++)
         {
            uchar byte_val = m_rx_buf[hdr_len + i];
            if(has_mask)
               byte_val ^= mask[i % 4];
            payload[i] = byte_val;
         }

         int total_frame_len = hdr_len + plen;
         int rem = m_rx_len - total_frame_len;
         if(rem > 0)
            ArrayCopy(m_rx_buf, m_rx_buf, 0, total_frame_len, rem);
         m_rx_len = rem;
         ArrayResize(m_rx_buf, m_rx_len);

         if(opcode == WS_OP_TEXT)
         {
            string msg = CharArrayToString(payload, 0, plen);
            if(m_on_message != NULL)
               m_on_message(msg);
         }
         else if(opcode == WS_OP_PING)
         {
            SendFrame(WS_OP_PONG, payload, plen);
         }
         else if(opcode == WS_OP_CLOSE)
         {
            SendFrame(WS_OP_CLOSE, payload, plen);
            Disconnect();
            return;
         }
      }
   }

public:
   CAurexisWebSocket()
   {
      m_socket = INVALID_HANDLE;
      m_state = WS_STATE_DISCONNECTED;
      m_is_tls = false;
      m_last_connect_time = 0;
      m_reconnect_delay = 5000;
      m_on_message = NULL;
      m_rx_len = 0;
      ArrayResize(m_rx_buf, 0);
   }

   ~CAurexisWebSocket()
   {
      Disconnect();
   }

   void SetMessageCallback(WsMessageCallback cb) { m_on_message = cb; }
   ENUM_WS_STATE GetState() const { return m_state; }
   bool IsConnected() const { return (m_state == WS_STATE_CONNECTED || m_state == WS_STATE_READY); }

   void Init(string host, uint port, string path, string token)
   {
      StringReplace(host, "https://", "");
      StringReplace(host, "http://", "");
      StringReplace(host, "wss://", "");
      StringReplace(host, "ws://", "");
      int slash_pos = StringFind(host, "/");
      if(slash_pos >= 0)
         host = StringSubstr(host, 0, slash_pos);

      m_host = host;
      m_port = port;
      m_path = path;
      m_token = token;
      m_is_tls = false;
   }

   bool Connect()
   {
      Disconnect();
      m_last_connect_time = GetTickCount();

      m_socket = SocketCreate();
      if(m_socket == INVALID_HANDLE)
      {
         Print("[AUREXIS WS] SocketCreate failed. Error: ", GetLastError());
         m_state = WS_STATE_DISCONNECTED;
         return false;
      }

      m_state = WS_STATE_CONNECTING;
      if(!SocketConnect(m_socket, m_host, m_port, 5000))
      {
         Print("[AUREXIS WS] SocketConnect to ", m_host, ":", m_port, " failed. Error: ", GetLastError());
         Disconnect();
         return false;
      }

      // Check whether TLS is already established (automatic on port 443 in MT5)
      string subject, issuer, serial, thumbprint;
      datetime expiration;
      m_is_tls = SocketTlsCertificate(m_socket, subject, issuer, serial, thumbprint, expiration);

      if(!m_is_tls && (m_port == 443 || m_port == 8443))
      {
         m_state = WS_STATE_TLS_HANDSHAKE;
         if(!SocketTlsHandshake(m_socket, m_host))
         {
            Print("[AUREXIS WS] SocketTlsHandshake failed. Error: ", GetLastError());
            Disconnect();
            return false;
         }
         m_is_tls = true;
         Print("[AUREXIS WS] SocketTlsHandshake completed successfully.");
      }
      else if(m_is_tls)
      {
         Print("[AUREXIS WS] TLS session established automatically. Certificate subject: ", subject);
      }

      SocketTimeouts(m_socket, 5000, 10);

      m_state = WS_STATE_WS_HANDSHAKE;
      if(!SendHttpUpgrade())
      {
         Print("[AUREXIS WS] SendHttpUpgrade failed.");
         Disconnect();
         return false;
      }

      return true;
   }

   void Disconnect()
   {
      if(m_socket != INVALID_HANDLE)
      {
         SocketClose(m_socket);
         m_socket = INVALID_HANDLE;
      }
      m_state = WS_STATE_DISCONNECTED;
      m_is_tls = false;
      m_rx_len = 0;
      ArrayResize(m_rx_buf, 0);
   }

   bool SendText(const string msg)
   {
      uchar payload[];
      StringToCharArray(msg, payload);
      int len = ArraySize(payload) - 1;
      return SendFrame(WS_OP_TEXT, payload, len);
   }

   void Tick()
   {
      if(m_state == WS_STATE_DISCONNECTED)
      {
         if(GetTickCount() - m_last_connect_time >= m_reconnect_delay)
         {
            Print("[AUREXIS WS] Attempting reconnection...");
            Connect();
         }
         return;
      }

      if(m_socket == INVALID_HANDLE || !SocketIsConnected(m_socket))
      {
         Print("[AUREXIS WS] Socket lost connection.");
         Disconnect();
         return;
      }

      uchar temp[4096];
      int read = 0;
      if(m_is_tls)
      {
         read = SocketTlsReadAvailable(m_socket, temp, 4096);
      }
      else
      {
         uint avail = SocketIsReadable(m_socket);
         if(avail > 0)
            read = SocketRead(m_socket, temp, 4096, 10);
      }

      if(read > 0)
      {
         int cur = m_rx_len;
         m_rx_len += read;
         ArrayResize(m_rx_buf, m_rx_len);
         ArrayCopy(m_rx_buf, temp, cur, 0, read);

         if(m_state == WS_STATE_WS_HANDSHAKE)
         {
            ProcessHttpUpgradeResponse();
         }
         if(m_state == WS_STATE_CONNECTED || m_state == WS_STATE_READY)
         {
            ProcessFrames();
         }
      }
      else if(read < 0)
      {
         int err = GetLastError();
         if(err != 0 && err != 5273)
         {
            Print("[AUREXIS WS] Socket read error: ", err);
            Disconnect();
         }
      }
   }
};
//+------------------------------------------------------------------+
