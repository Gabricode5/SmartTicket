from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()
# 1. L'adresse de ta base (récupérée de Docker ou en local par défaut)
# On utilise les identifiants que tu as configurés dans ton docker-compose
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:Password1234@postgres/ticketdb")

# 2. Création du moteur de connexion
engine = create_engine(DATABASE_URL)

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