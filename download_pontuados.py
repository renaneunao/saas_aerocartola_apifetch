#!/usr/bin/env python3
"""
Script para baixar dados de pontuados rodada por rodada e salvar em CSV
para análise em planilhas.
"""

import os
import csv
import json
import time
from pathlib import Path
from api_cartola import fetch_pontuados_data
from database import get_db_connection, close_db_connection

# Criar diretórios se não existirem
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data' / 'pontuados_baixados'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cache global de clubes e posições
CLUBES_CACHE = {}
POSICOES_CACHE = {}

def load_clubes_and_posicoes():
    """Carrega todos os clubes e posições uma vez no início"""
    global CLUBES_CACHE, POSICOES_CACHE
    
    conn = get_db_connection()
    if not conn:
        print("⚠️  Erro ao conectar ao banco para carregar clubes e posições")
        return
    
    try:
        # Carregar clubes
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, abreviacao FROM acf_clubes")
        for row in cursor.fetchall():
            clube_id, nome, abreviacao = row
            CLUBES_CACHE[clube_id] = nome or abreviacao or f"Clube_{clube_id}"
        
        # Carregar posições
        cursor.execute("SELECT id, nome, abreviacao FROM acf_posicoes")
        for row in cursor.fetchall():
            posicao_id, nome, abreviacao = row
            POSICOES_CACHE[posicao_id] = nome or abreviacao or f"Pos_{posicao_id}"
        
        cursor.close()
        print(f"✅ Cache carregado: {len(CLUBES_CACHE)} clubes, {len(POSICOES_CACHE)} posições")
    except Exception as e:
        print(f"⚠️  Erro ao carregar cache: {e}")
    finally:
        close_db_connection(conn)

def get_clube_name(clube_id):
    """Retorna o nome do clube do cache"""
    return CLUBES_CACHE.get(clube_id, f"Clube_{clube_id}")

def get_posicao_name(posicao_id):
    """Retorna o nome da posição do cache"""
    return POSICOES_CACHE.get(posicao_id, f"Pos_{posicao_id}")

def download_pontuados_rodada(rodada):
    """Baixa dados de pontuados de uma rodada e salva em CSV"""
    print(f"\n{'='*60}")
    print(f"Baixando pontuados da rodada {rodada}...")
    print(f"{'='*60}")
    
    # Buscar dados da API
    pontuados_data = fetch_pontuados_data(rodada)
    
    if not pontuados_data:
        print(f"⚠️  Nenhum dado encontrado para rodada {rodada}")
        return False
    
    if 'atletas' not in pontuados_data:
        print(f"⚠️  Formato de dados inválido para rodada {rodada}")
        return False
    
    # Preparar dados para CSV
    rows = []
    atletas = pontuados_data.get('atletas', {})
    
    for atleta_id, atleta in atletas.items():
        scout = atleta.get('scout', {}) or {}
        
        # Buscar nomes de clube e posição
        clube_id = atleta.get('clube_id', 0)
        posicao_id = atleta.get('posicao_id', 0)
        clube_nome = get_clube_name(clube_id)
        posicao_nome = get_posicao_name(posicao_id)
        
        row = {
            'rodada': rodada,
            'atleta_id': atleta_id,
            'apelido': atleta.get('apelido', ''),
            'clube_id': clube_id,
            'clube': clube_nome,
            'posicao_id': posicao_id,
            'posicao': posicao_nome,
            'pontuacao': atleta.get('pontuacao', 0.0),
            'entrou_em_campo': 'Sim' if atleta.get('entrou_em_campo', False) else 'Não',
            'foto': atleta.get('foto', ''),
            # Scouts - apenas siglas
            'G': scout.get('G', 0),
            'A': scout.get('A', 0),
            'FD': scout.get('FD', 0),
            'FF': scout.get('FF', 0),
            'DE': scout.get('DE', 0),
            'DS': scout.get('DS', 0),
            'FS': scout.get('FS', 0),
            'FC': scout.get('FC', 0),
            'CA': scout.get('CA', 0),
            'CV': scout.get('CV', 0),
            'GS': scout.get('GS', 0),
            'SG': scout.get('SG', 0),
            'I': scout.get('I', 0),
            'DP': scout.get('DP', 0),
            'FT': scout.get('FT', 0),
            'PC': scout.get('PC', 0),
            'PP': scout.get('PP', 0),
            'PS': scout.get('PS', 0),
            'V': scout.get('V', 0),
        }
        rows.append(row)
    
    if not rows:
        print(f"⚠️  Nenhum atleta encontrado para rodada {rodada}")
        return False
    
    # Ordenar por pontuação (maior primeiro)
    rows.sort(key=lambda x: x['pontuacao'], reverse=True)
    
    # Salvar em CSV
    filename = DATA_DIR / f'pontuados_rodada_{rodada:02d}.csv'
    fieldnames = [
        'rodada', 'atleta_id', 'apelido', 'clube_id', 'clube', 
        'posicao_id', 'posicao', 'pontuacao', 'entrou_em_campo', 'foto',
        'G', 'A', 'FD', 'FF', 'DE', 'DS', 'FS', 'FC', 'CA', 'CV', 
        'GS', 'SG', 'I', 'DP', 'FT', 'PC', 'PP', 'PS', 'V'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ Rodada {rodada}: {len(rows)} atletas salvos em {filename.name}")
    print(f"   Melhor pontuação: {rows[0]['pontuacao']:.2f} ({rows[0]['apelido']})")
    
    return True

def main():
    """Baixa pontuados de todas as rodadas disponíveis"""
    print("="*60)
    print("DOWNLOAD DE PONTUADOS POR RODADA")
    print("="*60)
    print(f"Diretório de saída: {DATA_DIR}")
    print()
    
    # Carregar cache de clubes e posições UMA VEZ
    print("📦 Carregando cache de clubes e posições...")
    load_clubes_and_posicoes()
    print()
    
    # Verificar rodadas disponíveis no banco
    conn = get_db_connection()
    rodadas_disponiveis = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT rodada_id FROM acf_pontuados ORDER BY rodada_id")
            rodadas_disponiveis = [row[0] for row in cursor.fetchall()]
            cursor.close()
        except Exception as e:
            print(f"⚠️  Erro ao buscar rodadas do banco: {e}")
        finally:
            close_db_connection(conn)
    
    if not rodadas_disponiveis:
        print("⚠️  Nenhuma rodada encontrada no banco. Tentando rodadas 1 a 37...")
        rodadas_disponiveis = list(range(1, 38))
    else:
        print(f"📊 Rodadas encontradas no banco: {min(rodadas_disponiveis)} a {max(rodadas_disponiveis)}")
        print(f"   Total: {len(rodadas_disponiveis)} rodadas")
    
    print(f"\n🔄 Iniciando download de {len(rodadas_disponiveis)} rodadas...\n")
    
    sucesso = 0
    falhas = 0
    
    for rodada in rodadas_disponiveis:
        try:
            if download_pontuados_rodada(rodada):
                sucesso += 1
            else:
                falhas += 1
            # Pequeno delay para não sobrecarregar a API
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Erro ao processar rodada {rodada}: {e}")
            falhas += 1
    
    print(f"\n{'='*60}")
    print("RESUMO DO DOWNLOAD")
    print(f"{'='*60}")
    print(f"✅ Sucesso: {sucesso} rodadas")
    print(f"❌ Falhas: {falhas} rodadas")
    print(f"📁 Arquivos salvos em: {DATA_DIR}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()

