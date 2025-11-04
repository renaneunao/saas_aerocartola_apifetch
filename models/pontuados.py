def update_pontuados(conn, pontuados_data, rodada):
    from psycopg2.extras import execute_values
    import time
    t0 = time.time()
    cursor = conn.cursor()
    # Se já existem pontuações para a rodada, pula
    cursor.execute('SELECT COUNT(*) FROM acf_pontuados WHERE rodada_id = %s', (rodada,))
    exists_count = cursor.fetchone()[0]
    if exists_count and exists_count > 0:
        print(f"Rodada {rodada} já existente em 'pontuados'. Pulando atualização.")
        return

    rows = []
    for atleta_id, atleta in pontuados_data['atletas'].items():
        scout = (atleta.get('scout', {}) or {})
        row = (
            int(atleta_id),
            rodada,
            atleta.get('clube_id', 0),
            atleta.get('posicao_id', 0),
            atleta.get('pontuacao', 0.0),
            atleta.get('entrou_em_campo', False),
            atleta.get('apelido', 'Desconhecido'),
            atleta.get('foto', ''),
            scout.get('A', 0), scout.get('CA', 0), scout.get('CV', 0), scout.get('DE', 0), scout.get('DS', 0),
            scout.get('FC', 0), scout.get('FD', 0), scout.get('FF', 0), scout.get('FS', 0), scout.get('G', 0),
            scout.get('GS', 0), scout.get('I', 0), scout.get('SG', 0)
        )
        rows.append(row)

    if not rows:
        print(f"Pontuados: nada para inserir na rodada {rodada}")
        return

    insert_sql = '''
        INSERT INTO acf_pontuados (
            atleta_id, rodada_id, clube_id, posicao_id, pontuacao, entrou_em_campo, apelido, foto,
            scout_a, scout_ca, scout_cv, scout_de, scout_ds, scout_fc, scout_fd, scout_ff, scout_fs,
            scout_g, scout_gs, scout_i, scout_sg
        ) VALUES %s
        ON CONFLICT (atleta_id, rodada_id) DO UPDATE SET
            clube_id = EXCLUDED.clube_id,
            posicao_id = EXCLUDED.posicao_id,
            pontuacao = EXCLUDED.pontuacao,
            entrou_em_campo = EXCLUDED.entrou_em_campo,
            apelido = EXCLUDED.apelido,
            foto = EXCLUDED.foto,
            scout_a = EXCLUDED.scout_a,
            scout_ca = EXCLUDED.scout_ca,
            scout_cv = EXCLUDED.scout_cv,
            scout_de = EXCLUDED.scout_de,
            scout_ds = EXCLUDED.scout_ds,
            scout_fc = EXCLUDED.scout_fc,
            scout_fd = EXCLUDED.scout_fd,
            scout_ff = EXCLUDED.scout_ff,
            scout_fs = EXCLUDED.scout_fs,
            scout_g = EXCLUDED.scout_g,
            scout_gs = EXCLUDED.scout_gs,
            scout_i = EXCLUDED.scout_i,
            scout_sg = EXCLUDED.scout_sg
    '''
    execute_values(cursor, insert_sql, rows, page_size=1000)
    conn.commit()
    print(f"Pontuados: rodada {rodada}, inseridos/atualizados {len(rows)} em {time.time()-t0:.2f}s")