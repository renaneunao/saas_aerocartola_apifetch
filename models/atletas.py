def create_atletas_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS atletas (
            atleta_id INTEGER PRIMARY KEY,
            rodada_id INTEGER,  -- Apenas para referência, não parte da chave
            clube_id INTEGER,
            posicao_id INTEGER,
            status_id INTEGER,
            pontos_num REAL,
            media_num REAL,
            variacao_num REAL,
            preco_num REAL,
            jogos_num INTEGER,
            entrou_em_campo BOOLEAN,
            slug TEXT,
            apelido TEXT,
            nome TEXT,
            foto TEXT,
            FOREIGN KEY (clube_id) REFERENCES clubes(id),
            FOREIGN KEY (posicao_id) REFERENCES posicoes(id),
            FOREIGN KEY (status_id) REFERENCES status(id)
        )
    ''')
    conn.commit()

def update_atletas(conn, atletas_data, rodada_atual):
    import time
    from psycopg2.extras import execute_values
    cursor = conn.cursor()
    t0 = time.time()
    # Sincroniza: remove atletas que não existem mais na API e upserta os atuais
    ids_novos = [a['atleta_id'] for a in atletas_data] if atletas_data else []

    if not ids_novos:
        cursor.execute('DELETE FROM atletas')
    else:
        # Delete eficiente usando ANY(array)
        cursor.execute("DELETE FROM atletas WHERE NOT (atleta_id = ANY(%s))", (ids_novos,))

    # Upsert em lote com execute_values (muito mais rápido)
    rows = [(
        a['atleta_id'], rodada_atual, a['clube_id'], a['posicao_id'], a['status_id'], a['pontos_num'],
        a['media_num'], a['variacao_num'], a['preco_num'], a['jogos_num'], a['entrou_em_campo'],
        a['slug'], a['apelido'], a['nome'], a['foto']
    ) for a in atletas_data]

    insert_sql = '''
        INSERT INTO atletas (atleta_id, rodada_id, clube_id, posicao_id, status_id, pontos_num,
                             media_num, variacao_num, preco_num, jogos_num, entrou_em_campo,
                             slug, apelido, nome, foto)
        VALUES %s
        ON CONFLICT (atleta_id) DO UPDATE SET
            rodada_id = EXCLUDED.rodada_id,
            clube_id = EXCLUDED.clube_id,
            posicao_id = EXCLUDED.posicao_id,
            status_id = EXCLUDED.status_id,
            pontos_num = EXCLUDED.pontos_num,
            media_num = EXCLUDED.media_num,
            variacao_num = EXCLUDED.variacao_num,
            preco_num = EXCLUDED.preco_num,
            jogos_num = EXCLUDED.jogos_num,
            entrou_em_campo = EXCLUDED.entrou_em_campo,
            slug = EXCLUDED.slug,
            apelido = EXCLUDED.apelido,
            nome = EXCLUDED.nome,
            foto = EXCLUDED.foto
    '''
    execute_values(cursor, insert_sql, rows, page_size=1000)
    conn.commit()
    t1 = time.time()
    print(f"Atletas: upsert {len(rows)} registros em {t1 - t0:.2f}s")