#!/usr/bin/env python3
"""
Script para inserir a credencial padrão do time Aero-RBSV no banco de dados.
Pode ser usado em produção ou desenvolvimento.

As credenciais são lidas do arquivo .env (variáveis AERO_RBSV_ACCESS_TOKEN, etc)
ou, como fallback, do arquivo refresh_token.json.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from database import get_db_connection, close_db_connection
from models.credenciais import insert_credencial, get_credencial_by_env_key

# Carregar variáveis de ambiente do .env
load_dotenv(encoding='utf-8')

def get_tokens_from_env():
    """Obtém tokens das variáveis de ambiente (.env)"""
    access_token = os.getenv('AERO_RBSV_ACCESS_TOKEN')
    refresh_token = os.getenv('AERO_RBSV_REFRESH_TOKEN')
    id_token = os.getenv('AERO_RBSV_ID_TOKEN')
    
    if access_token and refresh_token and id_token:
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'id_token': id_token
        }
    return None

def get_tokens_from_json():
    """Obtém tokens do arquivo JSON (fallback)"""
    json_path = Path(__file__).parent / 'refresh_token.json'
    
    if not json_path.exists():
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[AVISO] Erro ao ler JSON: {e}")
        return None

def main():
    """Insere a credencial padrão do time Aero-RBSV"""
    
    # Tentar obter tokens do .env primeiro
    tokens = get_tokens_from_env()
    
    # Se não encontrou no .env, tentar do JSON (fallback)
    if not tokens:
        print("[INFO] Tokens nao encontrados no .env, tentando do refresh_token.json...")
        tokens = get_tokens_from_json()
    
    if not tokens:
        print("[ERRO] Tokens nao encontrados nem no .env nem no refresh_token.json!")
        print("   Configure as variaveis AERO_RBSV_ACCESS_TOKEN, AERO_RBSV_REFRESH_TOKEN e AERO_RBSV_ID_TOKEN no .env")
        return False
    
    # Conectar ao banco
    conn = get_db_connection()
    if not conn:
        print("[ERRO] Falha ao conectar ao banco de dados")
        return False
    
    try:
        # Verificar se a credencial já existe
        existing_credential = get_credencial_by_env_key(conn, 'AERO_RBSV')
        
        if existing_credential:
            print("[INFO] Credencial 'Aero-RBSV' ja existe no banco de dados (ID: {})".format(existing_credential['id']))
            return True
        
        # Inserir credencial com estratégia 1 (só se não existir)
        insert_credencial(
            conn=conn,
            nome='Aero-RBSV',
            env_key='AERO_RBSV',
            access_token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            id_token=tokens.get('id_token'),
            estrategia=1
        )
        
        print("[OK] Credencial 'Aero-RBSV' inserida com sucesso!")
        print("   - env_key: AERO_RBSV")
        print("   - estrategia: 1")
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao inserir credencial: {e}")
        return False
    finally:
        close_db_connection(conn)

if __name__ == '__main__':
    main()

