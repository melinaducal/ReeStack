from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal, engine, Base
from app.models import User
from app.auth.utils import get_password_hash

client = TestClient(app)

# create test user if not exists
db = SessionLocal()
user = db.query(User).filter(User.email == 'testprofile@example.com').first()
if not user:
    user = User(
        username='testprofile',
        first_name='Test',
        last_name='Profile',
        email='testprofile@example.com',
        birth_date='1995-01-01',
        hashed_password=get_password_hash('Passw0rd!')
    )
    db.add(user)
    db.commit()
    db.refresh(user)
db.close()

# login
r = client.post('/auth/login', json={'email': 'testprofile@example.com', 'password': 'Passw0rd!'})
assert r.status_code == 200
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# get me
r = client.get('/users/me', headers=headers)
assert r.status_code == 200
me = r.json()
assert 'hashed_password' not in me
assert 'password' not in me

# update me
r = client.put('/users/me', headers=headers, json={'display_name': 'Test P', 'bio': 'Hola', 'username': 'testprofile2'})
if r.status_code == 400:
    # try different username
    r = client.put('/users/me', headers=headers, json={'display_name': 'Test P', 'bio': 'Hola'})
assert r.status_code == 200

# search
r = client.get('/users/search?q=test&page=1&limit=10')
assert r.status_code == 200

# public by id
r = client.get(f'/users/{me["id"]}/public')
assert r.status_code == 200
pub = r.json()
assert 'email' not in pub
assert 'hashed_password' not in pub
assert 'password' not in pub
assert 'stats' in pub

print('all tests passed')
