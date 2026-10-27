from app.database import SessionLocal
from app.models import User
from app.auth.utils import get_password_hash
from datetime import date

db = SessionLocal()
# Delete if exists
existing = db.query(User).filter(User.email == 'admin@reestack.com').first()
if existing:
    db.delete(existing)
    db.commit()

admin = User(
    username='admin',
    first_name='Admin',
    last_name='ReeStack',
    email='admin@reestack.com',
    birth_date=date(1990, 1, 1),
    hashed_password=get_password_hash('Admin123!')
)
db.add(admin)
db.commit()
print(admin.id)
db.close()
