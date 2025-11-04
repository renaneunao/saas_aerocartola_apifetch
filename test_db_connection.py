#!/usr/bin/env python3
"""Script para testar conexão com o banco de dados PostgreSQL"""

from database import get_db_connection, close_db_connection, test_connection
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv(encoding='utf-8')

def test_db_connection():
    """Testa a conexão com o banco de dados"""
    print("=" * 60)
    print("TESTE DE CONEXÃO COM BANCO DE DADOS")
    print("=" * 60)
    
    # Mostrar configurações (sem mostrar senha completa)
    print("\n📋 Configurações de conexão:")
    print(f"   Host: {os.getenv('POSTGRES_HOST', 'N/A')}")
    print(f"   Port: {os.getenv('POSTGRES_PORT', 'N/A')}")
    print(f"   User: {os.getenv('POSTGRES_USER', 'N/A')}")
    password = os.getenv('POSTGRES_PASSWORD', 'N/A')
    if password and password != 'N/A':
        print(f"   Password: {'*' * min(len(password), 10)}...")
    else:
        print(f"   Password: {password}")
    print(f"   Database: {os.getenv('POSTGRES_DB', 'cartola_manager')}")
    
    print("\n🔌 Testando conexão...")
    
    # Usar a função test_connection do database.py
    if test_connection():
        print("\n✅ Conexão estabelecida com sucesso!")
        
        # Tentar algumas queries simples
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Verificar versão do PostgreSQL
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                print(f"\n📊 Versão do PostgreSQL: {version.split(',')[0]}")
                
                # Verificar se o banco cartola_manager existe e tem tabelas
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = cursor.fetchall()
                print(f"\n📋 Tabelas encontradas ({len(tables)}):")
                for table in tables[:10]:  # Mostrar até 10 primeiras
                    print(f"   - {table[0]}")
                if len(tables) > 10:
                    print(f"   ... e mais {len(tables) - 10} tabela(s)")
                
                # Verificar credenciais
                cursor.execute("SELECT COUNT(*) FROM acf_credenciais;")
                cred_count = cursor.fetchone()[0]
                print(f"\n🔑 Credenciais no banco: {cred_count}")
                
                cursor.close()
                close_db_connection(conn)
                return True
                
            except Exception as e:
                print(f"\n⚠️  Conexão OK, mas erro ao executar queries: {e}")
                close_db_connection(conn)
                return False
    else:
        print("\n❌ Falha na conexão!")
        print("\n💡 Verifique:")
        print("   1. Se o PostgreSQL está rodando")
        print("   2. Se as credenciais no .env estão corretas")
        print("   3. Se o host e porta estão acessíveis")
        print("   4. Se o banco de dados existe")
        return False

if __name__ == '__main__':
    success = test_db_connection()
    exit(0 if success else 1)




