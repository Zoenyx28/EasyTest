"""End-to-end test for test management platform."""
import urllib.request, json, time

BASE = 'http://127.0.0.1:8086'

def get(path):
    r = urllib.request.urlopen(f'{BASE}{path}', timeout=30)
    return json.loads(r.read())

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f'{BASE}{path}', data=body,
        headers={'Content-Type': 'application/json'}, method='POST')
    r = urllib.request.urlopen(req, timeout=120)
    return json.loads(r.read())

def poll(run_id, max_wait=60):
    for i in range(max_wait):
        time.sleep(1)
        s = get(f'/api/run/{run_id}')
        if s['state'] != 'running':
            return s
        if i % 5 == 0 or s['completed'] > 0:
            print(f'  [{i+1}s] completed={s["completed"]}, passed={s["passed"]}, failed={s["failed"]}, broken={s["broken"]}')
    return get(f'/api/run/{run_id}')

# Test 1: Discovery
print('1. Discovery...')
d = get('/api/tests')
print(f'   total={d["total"]}, modules={len(d["modules"])}')

# Test 2: Single test
print('\n2. Single test execution...')
item = d['modules'][0]['classes'][0]['items'][0]
r = post('/api/run', {'uids': [item['uid']], 'concurrency': 1})
s = poll(r['run_id'], 30)
print(f'   Result: state={s["state"]}, completed={s["completed"]}, passed={s["passed"]}, broken={s["broken"]}')

# Test 3: Batch test with concurrency
print('\n3. Batch test (3 tests, concurrency=2)...')
uids = []
for mod in d['modules'][:2]:
    for cls in mod['classes'][:1]:
        for it in cls['items'][:2]:
            if len(uids) < 3:
                uids.append(it['uid'])
r = post('/api/run', {'uids': uids, 'concurrency': 2})
s = poll(r['run_id'], 60)
print(f'   Result: state={s["state"]}, completed={s["completed"]}, passed={s["passed"]}, broken={s["broken"]}')

# Test 4: All tests (smoke)
print('\n4. All tests (no uids, runs all 484)...')
r = post('/api/run', {'uids': [], 'concurrency': 4})
print(f'   run_id={r["run_id"]} - running all tests will take a while, check status later')

# Test 5: Report
print('\n5. Report...')
try:
    rep = get('/api/report/latest')
    print(f'   Summary: {json.dumps(rep, ensure_ascii=False)[:200]}')
except Exception as e:
    print(f'   Error: {e}')

print('\nAll tests complete!')
