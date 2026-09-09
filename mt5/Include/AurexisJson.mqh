//+------------------------------------------------------------------+
//|                                                  AurexisJson.mqh |
//|                                  Copyright 2026, AUREXIS Systems |
//|                                       https://app.aurexis.web.id |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, AUREXIS Systems"
#property link      "https://app.aurexis.web.id"
#property strict

enum ENUM_JSON_TYPE
{
   JSON_NULL,
   JSON_BOOL,
   JSON_NUMBER,
   JSON_STRING,
   JSON_ARRAY,
   JSON_OBJECT
};

class CJsonValue
{
private:
   ENUM_JSON_TYPE    m_type;
   bool              m_bool_val;
   double            m_num_val;
   string            m_str_val;
   CJsonValue*       m_elements[];
   string            m_keys[];
   int               m_count;

   void              Clear()
   {
      for(int i = 0; i < m_count; i++)
      {
         if(CheckPointer(m_elements[i]) == POINTER_DYNAMIC)
            delete m_elements[i];
      }
      ArrayResize(m_elements, 0);
      ArrayResize(m_keys, 0);
      m_count = 0;
      m_type = JSON_NULL;
      m_bool_val = false;
      m_num_val = 0.0;
      m_str_val = "";
   }

   static void SkipWhitespace(const string &src, int &pos, int len)
   {
      while(pos < len)
      {
         ushort ch = StringGetCharacter(src, pos);
         if(ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n')
            pos++;
         else
            break;
      }
   }

   static string ParseStringLiteral(const string &src, int &pos, int len)
   {
      pos++; // skip opening quote
      string res = "";
      while(pos < len)
      {
         ushort ch = StringGetCharacter(src, pos);
         if(ch == '"')
         {
            pos++;
            return res;
         }
         else if(ch == '\\')
         {
            pos++;
            if(pos >= len) break;
            ushort esc = StringGetCharacter(src, pos);
            if(esc == '"') res += "\"";
            else if(esc == '\\') res += "\\";
            else if(esc == '/') res += "/";
            else if(esc == 'b') res += ShortToString(8);
            else if(esc == 'f') res += ShortToString(12);
            else if(esc == 'n') res += "\n";
            else if(esc == 'r') res += "\r";
            else if(esc == 't') res += "\t";
            else if(esc == 'u')
            {
               pos += 4;
            }
            pos++;
         }
         else
         {
            StringAdd(res, ShortToString(ch));
            pos++;
         }
      }
      return res;
   }

public:
                     CJsonValue() : m_type(JSON_NULL), m_bool_val(false), m_num_val(0.0), m_str_val(""), m_count(0) {}
                    ~CJsonValue() { Clear(); }

   ENUM_JSON_TYPE    GetType() const { return m_type; }
   void              SetType(ENUM_JSON_TYPE t) { Clear(); m_type = t; }

   bool              GetBool() const { return m_bool_val; }
   void              SetBool(bool b) { Clear(); m_type = JSON_BOOL; m_bool_val = b; }

   double            GetNumber() const { return m_num_val; }
   void              SetNumber(double n) { Clear(); m_type = JSON_NUMBER; m_num_val = n; }

   string            GetString() const { return m_str_val; }
   void              SetString(string s) { Clear(); m_type = JSON_STRING; m_str_val = s; }

   int               GetSize() const { return m_count; }

   void              Add(CJsonValue *val)
   {
      if(m_type != JSON_ARRAY)
      {
         Clear();
         m_type = JSON_ARRAY;
      }
      ArrayResize(m_elements, m_count + 1);
      m_elements[m_count] = val;
      m_count++;
   }

   void              Set(string key, CJsonValue *val)
   {
      if(m_type != JSON_OBJECT)
      {
         Clear();
         m_type = JSON_OBJECT;
      }
      for(int i = 0; i < m_count; i++)
      {
         if(m_keys[i] == key)
         {
            if(CheckPointer(m_elements[i]) == POINTER_DYNAMIC)
               delete m_elements[i];
            m_elements[i] = val;
            return;
         }
      }
      ArrayResize(m_keys, m_count + 1);
      ArrayResize(m_elements, m_count + 1);
      m_keys[m_count] = key;
      m_elements[m_count] = val;
      m_count++;
   }

   void              SetString(string key, string val)
   {
      CJsonValue *jv = new CJsonValue();
      jv.SetString(val);
      Set(key, jv);
   }

   void              SetNumber(string key, double val)
   {
      CJsonValue *jv = new CJsonValue();
      jv.SetNumber(val);
      Set(key, jv);
   }

   void              SetBool(string key, bool val)
   {
      CJsonValue *jv = new CJsonValue();
      jv.SetBool(val);
      Set(key, jv);
   }

   void              SetNull(string key)
   {
      CJsonValue *jv = new CJsonValue();
      jv.SetType(JSON_NULL);
      Set(key, jv);
   }

   CJsonValue*       Get(string key) const
   {
      if(m_type != JSON_OBJECT) return NULL;
      for(int i = 0; i < m_count; i++)
      {
         if(m_keys[i] == key)
            return m_elements[i];
      }
      return NULL;
   }

   CJsonValue*       GetAt(int idx) const
   {
      if((m_type != JSON_ARRAY && m_type != JSON_OBJECT) || idx < 0 || idx >= m_count)
         return NULL;
      return m_elements[idx];
   }

   string            GetKeyAt(int idx) const
   {
      if(m_type != JSON_OBJECT || idx < 0 || idx >= m_count)
         return "";
      return m_keys[idx];
   }

   string            GetString(string key, string def_val = "") const
   {
      CJsonValue *v = Get(key);
      if(v == NULL) return def_val;
      if(v.GetType() == JSON_STRING) return v.GetString();
      if(v.GetType() == JSON_NUMBER) return DoubleToString(v.GetNumber(), 2);
      if(v.GetType() == JSON_BOOL) return v.GetBool() ? "true" : "false";
      return def_val;
   }

   double            GetDouble(string key, double def_val = 0.0) const
   {
      CJsonValue *v = Get(key);
      if(v == NULL) return def_val;
      if(v.GetType() == JSON_NUMBER) return v.GetNumber();
      if(v.GetType() == JSON_STRING) return StringToDouble(v.GetString());
      return def_val;
   }

   long              GetLong(string key, long def_val = 0) const
   {
      CJsonValue *v = Get(key);
      if(v == NULL) return def_val;
      if(v.GetType() == JSON_NUMBER) return (long)v.GetNumber();
      if(v.GetType() == JSON_STRING) return StringToInteger(v.GetString());
      return def_val;
   }

   bool              GetBool(string key, bool def_val = false) const
   {
      CJsonValue *v = Get(key);
      if(v == NULL) return def_val;
      if(v.GetType() == JSON_BOOL) return v.GetBool();
      return def_val;
   }

   static string EscapeString(const string &s)
   {
      string out = "";
      int len = StringLen(s);
      for(int i = 0; i < len; i++)
      {
         ushort ch = StringGetCharacter(s, i);
         if(ch == '"') out += "\\\"";
         else if(ch == '\\') out += "\\\\";
         else if(ch == 8) out += "\\b";
         else if(ch == 12) out += "\\f";
         else if(ch == '\n') out += "\\n";
         else if(ch == '\r') out += "\\r";
         else if(ch == '\t') out += "\\t";
         else out += ShortToString(ch);
      }
      return out;
   }
   string            Serialize() const
   {
      switch(m_type)
      {
         case JSON_NULL:
            return "null";
         case JSON_BOOL:
            return m_bool_val ? "true" : "false";
         case JSON_NUMBER:
            if(m_num_val == (long)m_num_val)
               return IntegerToString((long)m_num_val);
            else
               return DoubleToString(m_num_val, 8);
         case JSON_STRING:
            return "\"" + EscapeString(m_str_val) + "\"";
         case JSON_ARRAY:
         {
            string out = "[";
            for(int i = 0; i < m_count; i++)
            {
               if(i > 0) out += ",";
               if(m_elements[i] != NULL)
                  out += m_elements[i].Serialize();
               else
                  out += "null";
            }
            out += "]";
            return out;
         }
         case JSON_OBJECT:
         {
            string out = "{";
            for(int i = 0; i < m_count; i++)
            {
               if(i > 0) out += ",";
               out += "\"" + EscapeString(m_keys[i]) + "\":";
               if(m_elements[i] != NULL)
                  out += m_elements[i].Serialize();
               else
                  out += "null";
            }
            out += "}";
            return out;
         }
      }
      return "null";
   }

   static CJsonValue* Parse(const string &src, int &pos, int len)
   {
      SkipWhitespace(src, pos, len);
      if(pos >= len) return NULL;

      ushort ch = StringGetCharacter(src, pos);
      if(ch == '{')
      {
         pos++;
         CJsonValue *obj = new CJsonValue();
         obj.SetType(JSON_OBJECT);
         while(pos < len)
         {
            SkipWhitespace(src, pos, len);
            if(pos >= len) break;
            ushort c = StringGetCharacter(src, pos);
            if(c == '}')
            {
               pos++;
               return obj;
            }
            if(c == ',')
            {
               pos++;
               continue;
            }
            if(c == '"')
            {
               string key = ParseStringLiteral(src, pos, len);
               SkipWhitespace(src, pos, len);
               if(pos < len && StringGetCharacter(src, pos) == ':')
               {
                  pos++;
                  CJsonValue *val = Parse(src, pos, len);
                  if(val != NULL)
                     obj.Set(key, val);
               }
            }
            else
            {
               pos++;
            }
         }
         return obj;
      }
      else if(ch == '[')
      {
         pos++;
         CJsonValue *arr = new CJsonValue();
         arr.SetType(JSON_ARRAY);
         while(pos < len)
         {
            SkipWhitespace(src, pos, len);
            if(pos >= len) break;
            ushort c = StringGetCharacter(src, pos);
            if(c == ']')
            {
               pos++;
               return arr;
            }
            if(c == ',')
            {
               pos++;
               continue;
            }
            CJsonValue *val = Parse(src, pos, len);
            if(val != NULL)
               arr.Add(val);
         }
         return arr;
      }
      else if(ch == '"')
      {
         string str = ParseStringLiteral(src, pos, len);
         CJsonValue *val = new CJsonValue();
         val.SetString(str);
         return val;
      }
      else if(ch == 't' || ch == 'T')
      {
         if(StringSubstr(src, pos, 4) == "true" || StringSubstr(src, pos, 4) == "TRUE")
         {
            pos += 4;
            CJsonValue *val = new CJsonValue();
            val.SetBool(true);
            return val;
         }
      }
      else if(ch == 'f' || ch == 'F')
      {
         if(StringSubstr(src, pos, 5) == "false" || StringSubstr(src, pos, 5) == "FALSE")
         {
            pos += 5;
            CJsonValue *val = new CJsonValue();
            val.SetBool(false);
            return val;
         }
      }
      else if(ch == 'n' || ch == 'N')
      {
         if(StringSubstr(src, pos, 4) == "null" || StringSubstr(src, pos, 4) == "NULL")
         {
            pos += 4;
            CJsonValue *val = new CJsonValue();
            val.SetType(JSON_NULL);
            return val;
         }
      }
      else if(ch == '-' || (ch >= '0' && ch <= '9'))
      {
         int start = pos;
         if(ch == '-') pos++;
         while(pos < len)
         {
            ushort d = StringGetCharacter(src, pos);
            if((d >= '0' && d <= '9') || d == '.' || d == 'e' || d == 'E' || d == '+' || d == '-')
               pos++;
            else
               break;
         }
         string num_str = StringSubstr(src, start, pos - start);
         double num = StringToDouble(num_str);
         CJsonValue *val = new CJsonValue();
         val.SetNumber(num);
         return val;
      }

      pos++;
      return NULL;
   }

   static CJsonValue* Parse(const string &src)
   {
      int pos = 0;
      int len = StringLen(src);
      return Parse(src, pos, len);
   }
};
//+------------------------------------------------------------------+

