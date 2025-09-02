from sqlalchemy import (
    Column, Integer, String, Date, Numeric, Boolean, ForeignKey, Text,
    create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///vacaciones.db")
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()

class Empleado(Base):
    __tablename__ = "empleados"
    id = Column(Integer, primary_key=True)
    numero_emp = Column(String(32), unique=True, nullable=False)
    nombre = Column(Text, nullable=False)
    nombre_corto = Column(Text)
    area = Column(String(64))
    turno = Column(String(16))         # T1/T2/T3 (si aplica)
    planta = Column(String(16))        # "Planta 1" / "Planta 3"
    foto_url = Column(Text)
    activo = Column(Boolean, default=True)

class Vacacion(Base):
    __tablename__ = "vacaciones"
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey("empleados.id", ondelete="CASCADE"), nullable=False)
    fecha_inicial = Column(Date, nullable=False)
    fecha_final = Column(Date, nullable=False)
    tipo = Column(String(64), nullable=False)  # p.ej. "Gozo de Vacaciones"
    gozo = Column(Numeric(4,1))                # admite 1.5 para 1/2 día
    fuente = Column(String(16), default="manual")

    empleado = relationship("Empleado")

def init_db():
    Base.metadata.create_all(engine)
