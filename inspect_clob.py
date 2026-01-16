from py_clob_client.client import ClobClient
import inspect

print("Methods in ClobClient:")
for name, data in inspect.getmembers(ClobClient):
    if name.startswith('__'): continue
    print(name)
