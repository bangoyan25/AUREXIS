#!/bin/bash
cd /home/ubuntu/AUREXIS
TOKEN=$(.venv/bin/python scripts/gen_token.py)
curl -s "http://localhost:8000/api/v1/market/26597c4f-19a0-41d3-85f7-ae6197cc31fb/state" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))"
