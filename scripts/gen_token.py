import sys
from backend.services.auth import create_access_token

uid = sys.argv[1] if len(sys.argv) > 1 else "0e79bf5f-1e36-44cf-bf5f-8f55a8dd1193"
print(create_access_token(uid))
