import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env com encoding utf-8
load_dotenv(encoding='utf-8')

# Configurações do PostgreSQL via variáveis de ambiente (obrigatórias)
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)) if os.getenv('POSTGRES_PORT') else 5432,
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'database': os.getenv('POSTGRES_DB')
}

# Validar se todas as variáveis obrigatórias foram fornecidas
required_vars_map = {
    'POSTGRES_HOST': 'host',
    'POSTGRES_USER': 'user', 
    'POSTGRES_PASSWORD': 'password',
    'POSTGRES_DB': 'database'
}
missing_vars = [env_var for env_var, config_key in required_vars_map.items() if not POSTGRES_CONFIG.get(config_key)]

if missing_vars:
    raise ValueError(f"Variáveis de ambiente obrigatórias não encontradas no .env: {', '.join(missing_vars)}")

def get_db_connection():
    """Conecta ao banco de dados PostgreSQL"""
    try:
        # Garantir que valores None não sejam passados
        config = {k: v for k, v in POSTGRES_CONFIG.items() if v is not None}
        conn = psycopg2.connect(**config)
        conn.autocommit = False
        return conn
    except (psycopg2.Error, UnicodeDecodeError, ValueError) as e:
        print(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

def close_db_connection(conn):
    """Fecha a conexão com o banco de dados"""
    if conn:
        try:
            conn.close()
        except psycopg2.Error as e:
            print(f"Erro ao fechar conexão: {e}")

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """Executa uma query e retorna o resultado"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)
        
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor.rowcount
        
        conn.commit()
        cursor.close()
        return result
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"Erro na query: {e}")
        return None
    finally:
        close_db_connection(conn)

def test_connection():
    """Testa a conexão com o banco"""
    conn = get_db_connection()
    if conn:
        print("✅ Conexão com PostgreSQL estabelecida com sucesso!")
        close_db_connection(conn)
        return True
    else:
        print("❌ Falha na conexão com PostgreSQL")
        return False