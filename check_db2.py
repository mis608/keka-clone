import os
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.getenv('SUPABASE_URL')
k1 = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_SECRET_KEY')
k2 = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_PUBLISHABLE_KEY')

cands = []
if k1: cands.append(('SERVICE', k1))
if k2: cands.append(('KEY', k2))
print('URL repr:', repr(url))
for n, k in cands:
    print(n, 'len', len(k), 'head', repr(k[:12]), 'tail', repr(k[-6:]))
    try:
        c = create_client(url, k)
        print(n, 'client created OK ->', c)
    except Exception as e:
        print(n, 'FAIL', type(e).__name__, e)
