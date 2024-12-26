from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
import uuid

# -------------------------------------------------------------------------
# 1) Configuração do Banco de Dados
# -------------------------------------------------------------------------
DATABASE_URL = "postgresql+psycopg2://catalog_user:catalog_pass@localhost:5432/catalog_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -------------------------------------------------------------------------
# 2) Modelos de Banco de Dados (SQLAlchemy)
# -------------------------------------------------------------------------
class Domain(Base):
    __tablename__ = "domains"
    domainId = Column(String, primary_key=True, index=True)
    domainName = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    subdomains = relationship("SubDomain", back_populates="domain")

class SubDomain(Base):
    __tablename__ = "subdomains"
    subDomainId = Column(String, primary_key=True, index=True)
    subDomainName = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    domainId = Column(String, ForeignKey("domains.domainId"), nullable=False)
    domain = relationship("Domain", back_populates="subdomains")
    catalogs = relationship("Catalog", back_populates="subdomain")

class Catalog(Base):
    __tablename__ = "catalogs"
    catalogId = Column(String, primary_key=True, index=True)
    catalogName = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    subDomainId = Column(String, ForeignKey("subdomains.subDomainId"), nullable=False)
    subdomain = relationship("SubDomain", back_populates="catalogs")
    schemas = relationship("Schema", back_populates="catalog")

class Schema(Base):
    __tablename__ = "schemas"
    schemaId = Column(String, primary_key=True, index=True)
    schemaName = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    catalogId = Column(String, ForeignKey("catalogs.catalogId"), nullable=False)
    catalog = relationship("Catalog", back_populates="schemas")
    tables = relationship("Table", back_populates="schema")

class Table(Base):
    __tablename__ = "tables"
    tableId = Column(String, primary_key=True, index=True)
    tableName = Column(String, nullable=False)
    schemaId = Column(String, ForeignKey("schemas.schemaId"), nullable=False)
    location = Column(Text, nullable=True)
    format = Column(String, nullable=True, default="iceberg")
    schema = relationship("Schema", back_populates="tables")

# Cria as tabelas no banco de dados.
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------------
# 3) Função de Dependência para Sessão
# -------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------------
# 4) Inicialização do FastAPI
# -------------------------------------------------------------------------
app = FastAPI(title="SGBD API com PostgreSQL via Docker")

# -------------------------------------------------------------------------
# 5) Modelos Pydantic (Request/Response)
# -------------------------------------------------------------------------
class DomainCreate(BaseModel):
    domainName: str
    description: Optional[str] = None

class DomainResponse(BaseModel):
    domainId: str
    domainName: str
    description: Optional[str]

    class Config:
        from_attributes = True

class SubDomainCreate(BaseModel):
    subDomainName: str
    description: Optional[str] = None

class SubDomainResponse(BaseModel):
    subDomainId: str
    subDomainName: str
    description: Optional[str]
    domainId: str

    class Config:
        from_attributes = True

class CatalogCreate(BaseModel):
    catalogName: str
    description: Optional[str] = None

class CatalogResponse(BaseModel):
    catalogId: str
    catalogName: str
    description: Optional[str]
    subDomainId: str

    class Config:
        from_attributes = True

class SchemaCreate(BaseModel):
    schemaName: str
    description: Optional[str] = None

class SchemaResponse(BaseModel):
    schemaId: str
    schemaName: str
    description: Optional[str]
    catalogId: str

    class Config:
        from_attributes = True

class TableCreate(BaseModel):
    tableName: str
    location: Optional[str] = None
    format: Optional[str] = "iceberg"

class TableResponse(BaseModel):
    tableId: str
    tableName: str
    location: Optional[str]
    format: Optional[str]
    schemaId: str

    class Config:
        from_attributes = True

# -------------------------------------------------------------------------
# 6) Endpoints para Domínios
# -------------------------------------------------------------------------
@app.get("/domains", response_model=List[DomainResponse])
def list_domains(db: Session = Depends(get_db)):
    domains = db.query(Domain).all()
    return domains

@app.post("/domains", response_model=DomainResponse, status_code=201)
def create_domain(domain: DomainCreate, db: Session = Depends(get_db)):
    domain_id = f"dom-{uuid.uuid4().hex[:6]}"
    new_domain = Domain(
        domainId=domain_id,
        domainName=domain.domainName,
        description=domain.description,
    )
    db.add(new_domain)
    db.commit()
    db.refresh(new_domain)
    return new_domain

@app.get("/domains/{domainId}", response_model=DomainResponse)
def get_domain(domainId: str, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.domainId == domainId).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    return domain

@app.delete("/domains/{domainId}", status_code=204)
def delete_domain(domainId: str, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.domainId == domainId).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    db.delete(domain)
    db.commit()
    return

# -------------------------------------------------------------------------
# 7) Endpoints para SubDomínios
# -------------------------------------------------------------------------
@app.get("/domains/{domainId}/subdomains", response_model=List[SubDomainResponse])
def list_subdomains(domainId: str, db: Session = Depends(get_db)):
    subdomains = db.query(SubDomain).filter(SubDomain.domainId == domainId).all()
    return subdomains

@app.post("/domains/{domainId}/subdomains", response_model=SubDomainResponse, status_code=201)
def create_subdomain(domainId: str, subdomain: SubDomainCreate, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.domainId == domainId).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain does not exist.")
    subdomain_id = f"sd-{uuid.uuid4().hex[:6]}"
    new_subdomain = SubDomain(
        subDomainId=subdomain_id,
        subDomainName=subdomain.subDomainName,
        description=subdomain.description,
        domainId=domainId,
    )
    db.add(new_subdomain)
    db.commit()
    db.refresh(new_subdomain)
    return new_subdomain

# -------------------------------------------------------------------------
# 8) Endpoints para Catálogos
# -------------------------------------------------------------------------
@app.get("/domains/{domainId}/subdomains/{subDomainId}/catalogs", response_model=List[CatalogResponse])
def list_catalogs(domainId: str, subDomainId: str, db: Session = Depends(get_db)):
    catalogs = db.query(Catalog).filter(Catalog.subDomainId == subDomainId).all()
    return catalogs

@app.post("/domains/{domainId}/subdomains/{subDomainId}/catalogs", response_model=CatalogResponse, status_code=201)
def create_catalog(domainId: str, subDomainId: str, catalog: CatalogCreate, db: Session = Depends(get_db)):
    subdomain = db.query(SubDomain).filter(SubDomain.subDomainId == subDomainId).first()
    if not subdomain:
        raise HTTPException(status_code=404, detail="Subdomain does not exist.")
    catalog_id = f"cat-{uuid.uuid4().hex[:6]}"
    new_catalog = Catalog(
        catalogId=catalog_id,
        catalogName=catalog.catalogName,
        description=catalog.description,
        subDomainId=subDomainId,
    )
    db.add(new_catalog)
    db.commit()
    db.refresh(new_catalog)
    return new_catalog

# -------------------------------------------------------------------------
# 9) Endpoints para Schemas
# -------------------------------------------------------------------------
@app.get("/catalogs/{catalogId}/schemas", response_model=List[SchemaResponse])
def list_schemas(catalogId: str, db: Session = Depends(get_db)):
    schemas = db.query(Schema).filter(Schema.catalogId == catalogId).all()
    return schemas

@app.post("/catalogs/{catalogId}/schemas", response_model=SchemaResponse, status_code=201)
def create_schema(catalogId: str, schema: SchemaCreate, db: Session = Depends(get_db)):
    catalog = db.query(Catalog).filter(Catalog.catalogId == catalogId).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog does not exist.")
    schema_id = f"sch-{uuid.uuid4().hex[:6]}"
    new_schema = Schema(
        schemaId=schema_id,
        schemaName=schema.schemaName,
        description=schema.description,
        catalogId=catalogId,
    )
    db.add(new_schema)
    db.commit()
    db.refresh(new_schema)
    return new_schema

# -------------------------------------------------------------------------
# 10) Endpoints para Tabelas
# -------------------------------------------------------------------------
@app.get("/schemas/{schemaId}/tables", response_model=List[TableResponse])
def list_tables(schemaId: str, db: Session = Depends(get_db)):
    tables = db.query(Table).filter(Table.schemaId == schemaId).all()
    return tables

@app.post("/schemas/{schemaId}/tables", response_model=TableResponse, status_code=201)
def create_table(schemaId: str, table: TableCreate, db: Session = Depends(get_db)):
    schema = db.query(Schema).filter(Schema.schemaId == schemaId).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema does not exist.")
    table_id = f"tbl-{uuid.uuid4().hex[:6]}"
    new_table = Table(
        tableId=table_id,
        tableName=table.tableName,
        location=table.location,
        format=table.format,
        schemaId=schemaId,
    )
    db.add(new_table)
    db.commit()
    db.refresh(new_table)
    return new_table
