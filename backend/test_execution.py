"""Test execution creation with > 50 cases."""
import urllib.request
import json
import time

BASE = 'http://localhost:8000'

# Get all cases for project 2
resp = urllib.request.urlopen(f'{BASE}/api/projects/2/cases?page=1&size=200')
resp_data = json.loads(resp.read().decode())
cases = resp_data.get('data', {}).get('items', [])
print(f'Total cases: {len(cases)}')

# Create a task with 80 cases (> 50)
uids = [c['uid'] for c in cases[:80]]
print(f'Creating task with {len(uids)} uids')

data = json.dumps({'name': 'TestTask-80-cases', 'uids': uids, 'project_id': 2}).encode('utf-8')
req = urllib.request.Request(f'{BASE}/api/tasks', data=data, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
task_result = json.loads(resp.read().decode())
print('Task result:', task_result)
task_id = task_result['data']['task_id']

# Create execution
data = json.dumps({'task_id': task_id, 'concurrency': 2, 'env': 'test'}).encode('utf-8')
req = urllib.request.Request(f'{BASE}/api/executions', data=data, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
exec_result = json.loads(resp.read().decode())
print('Execution result:', exec_result)

# Check executions list
time.sleep(1)
resp = urllib.request.urlopen(f'{BASE}/api/executions?project_id=2')
exec_list = json.loads(resp.read().decode())
items = exec_list.get('data', {}).get('items', [])
print(f'Executions list: {len(items)} items')
for item in items:
    print(f'  {item["execution_id"]} - {item["task_name"]} - {item["status"]} - total={item["total"]}')