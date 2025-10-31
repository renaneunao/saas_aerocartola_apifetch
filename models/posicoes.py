def update_posicoes(conn, posicoes_data):
    cursor = conn.cursor()
    for posicao_id, posicao in posicoes_data.items():
        cursor.execute('''
            INSERT INTO posicoes (id, nome, abreviacao)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                nome = EXCLUDED.nome,
                abreviacao = EXCLUDED.abreviacao
        ''', (int(posicao_id), posicao['nome'], posicao['abreviacao']))
    conn.commit()