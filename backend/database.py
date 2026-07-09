from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()
# 1. L'adresse de ta base — aucune valeur par défaut avec un mot de passe en dur : DATABASE_URL
# doit être défini explicitement (via .env en local, cf. .env.example, ou par l'hébergeur en
# prod), même pattern que SECRET_KEY dans main.py.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL manquante. Définis-la dans l'environnement (voir .env.example).")

# 2. Création du moteur de connexion
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

# 3. Création de la fabrique de sessions (pour lire/écrire)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# class pour géré les tables avec SQAlchemy. On l'utilisera dans models.py
Base = declarative_base()

# utilisation de la bd dans mes routes api
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
