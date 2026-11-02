from app.database import SessionLocal
from app.models import User
from app.auth.utils import get_password_hash
from datetime import date

db = SessionLocal()
user = db.query(User).filter(User.email == 'testprofile@example.com').first()
if not user:
    user = User(
        username='testprofile',
        first_name='Test',
        last_name='Profile',
        email='testprofile@example.com',
        birth_date=date(1995, 1, 1),
        hashed_password=get_password_hash('Passw0rd!')
    )
    db.add(user)
    db.commit()
    db.refresh(user)
db.close()
print('ok')
