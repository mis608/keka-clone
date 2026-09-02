import os
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
url = os.getenv('SUPABASE_URL')
keys = {
    'service': os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_SECRET_KEY'),
    'anon': os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_PUBLISHABLE_KEY'),
}
print('URL:', url)
for name, key in keys.items():
    if not key:
        print(name, 'NOT SET')
        continue
    try:
        c = create_client(url, key)
        r = c.table('employees').select('id').limit(3).execute()
        print(name, 'OK rows:', len(r.data))
    except Exception as e:
        print(name, 'FAIL:', e)
