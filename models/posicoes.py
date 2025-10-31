def create_posicoes_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posicoes (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            abreviacao TEXT
        )
    ''')
    conn.commit()

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