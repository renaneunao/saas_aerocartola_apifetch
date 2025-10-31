import psycopg2
from psycopg2.extras import RealDictCursor
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env com encoding utf-8
load_dotenv(encoding='utf-8')

# Configurações do PostgreSQL via variáveis de ambiente (obrigatórias)
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)) if os.getenv('POSTGRES_PORT') else 5432,
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'database': os.getenv('POSTGRES_DB', 'cartola_manager')  # Usa cartola_manager como padrão
}

# Validar se todas as variáveis obrigatórias foram fornecidas
# POSTGRES_DB não é obrigatório, será sempre cartola_manager
required_vars_map = {
    'POSTGRES_HOST': 'host',
    'POSTGRES_USER': 'user', 
    'POSTGRES_PASSWORD': 'password'
}
missing_vars = [env_var for env_var, config_key in required_vars_map.items() if not POSTGRES_CONFIG.get(config_key)]

if missing_vars:
    raise ValueError(f"Variáveis de ambiente obrigatórias não encontradas no .env: {', '.join(missing_vars)}")

# Garantir que o nome do banco seja sempre cartola_manager
POSTGRES_CONFIG['database'] = 'cartola_manager'

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

def create_database_if_not_exists():
    """Cria o banco de dados cartola_manager se ele não existir"""
    # Conectar ao banco padrão do PostgreSQL (postgres) para criar o banco
    config_without_db = {
        'host': POSTGRES_CONFIG['host'],
        'port': POSTGRES_CONFIG['port'],
        'user': POSTGRES_CONFIG['user'],
        'password': POSTGRES_CONFIG['password'],
        'database': 'postgres'  # Conectar ao banco padrão
    }
    
    db_name = 'cartola_manager'  # Nome fixo do banco de dados
    
    try:
        # Conectar ao banco padrão
        conn = psycopg2.connect(**config_without_db)
        conn.autocommit = True  # Necessário para criar banco de dados
        
        cursor = conn.cursor()
        
        # Verificar se o banco existe
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        
        exists = cursor.fetchone()
        
        if not exists:
            # Criar o banco de dados
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✅ Banco de dados '{db_name}' criado com sucesso!")
        else:
            print(f"ℹ️  Banco de dados '{db_name}' já existe.")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Erro ao criar banco de dados: {e}")
        return False

def initialize_database():
    """Inicializa o banco de dados executando o arquivo init.sql"""
    # Primeiro, criar o banco se não existir
    if not create_database_if_not_exists():
        print("❌ Falha ao criar/verificar banco de dados")
        return False
    
    # Agora conectar ao banco e executar o init.sql
    conn = get_db_connection()
    if not conn:
        print("❌ Falha ao conectar ao banco de dados para inicialização")
        return False
    
    try:
        # Ler o arquivo init.sql
        init_sql_path = Path(__file__).parent / 'init.sql'
        if not init_sql_path.exists():
            print(f"❌ Arquivo init.sql não encontrado em {init_sql_path}")
            return False
        
        with open(init_sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Dividir o SQL em instruções individuais e executar uma por uma
        cursor = conn.cursor()
        # Dividir por ponto-e-vírgula e filtrar instruções vazias
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        for statement in statements:
            # Remover comentários de linha (-- até o fim da linha)
            lines = []
            for line in statement.split('\n'):
                if '--' in line:
                    # Manter apenas a parte antes do comentário
                    comment_pos = line.find('--')
                    if comment_pos >= 0:
                        line = line[:comment_pos].rstrip()
                if line.strip():
                    lines.append(line)
            
            cleaned_statement = '\n'.join(lines).strip()
            if cleaned_statement:  # Pular strings vazias após limpeza
                cursor.execute(cleaned_statement)
        
        conn.commit()
        cursor.close()
        
        print("✅ Banco de dados inicializado com sucesso!")
        
        # Verificar e inserir credencial padrão do .env se necessário
        try:
            from insert_default_credential import main as insert_credential_main
            print("ℹ️  Verificando credencial padrão Aero-RBSV...")
            insert_credential_main()
        except ImportError:
            print("⚠️  Script insert_default_credential.py não encontrado. Credencial padrão não será inserida.")
        except Exception as e:
            print(f"⚠️  Erro ao verificar/inserir credencial padrão: {e}")
        
        return True
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Erro ao inicializar banco de dados: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro ao ler arquivo init.sql: {e}")
        return False
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