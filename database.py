import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# Configurações do PostgreSQL via variáveis de ambiente
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'password'),
    'database': os.getenv('POSTGRES_DB', 'cartola_manager')
}

def get_db_connection():
    """Conecta ao banco de dados PostgreSQL"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        conn.autocommit = False
        return conn
    except psycopg2.Error as e:
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