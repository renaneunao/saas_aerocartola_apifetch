def create_partidas_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partidas (
            partida_id INTEGER PRIMARY KEY,
            rodada_id INTEGER,
            clube_casa_id INTEGER,
            clube_visitante_id INTEGER,
            placar_oficial_mandante INTEGER,
            placar_oficial_visitante INTEGER,
            local TEXT,
            partida_data TEXT,
            valida BOOLEAN,
            timestamp INTEGER,
            FOREIGN KEY (clube_casa_id) REFERENCES clubes(id),
            FOREIGN KEY (clube_visitante_id) REFERENCES clubes(id)
        )
    ''')
    conn.commit()

def update_partidas(conn, partidas_data, rodada):
    cursor = conn.cursor()
    # Se já existem partidas cadastradas para a rodada, pula
    cursor.execute('SELECT COUNT(*) FROM partidas WHERE rodada_id = %s', (rodada,))
    exists_count = cursor.fetchone()[0]
    if exists_count and exists_count > 0:
        print(f"Rodada {rodada} já existente em 'partidas'. Pulando atualização.")
        return
    for partida in partidas_data['partidas']:
        cursor.execute('''
            INSERT INTO partidas (partida_id, rodada_id, clube_casa_id, clube_visitante_id, 
                                            placar_oficial_mandante, placar_oficial_visitante, local, 
                                            partida_data, valida, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (partida_id) 
            DO UPDATE SET rodada_id = EXCLUDED.rodada_id, clube_casa_id = EXCLUDED.clube_casa_id, 
                         clube_visitante_id = EXCLUDED.clube_visitante_id, 
                         placar_oficial_mandante = EXCLUDED.placar_oficial_mandante, 
                         placar_oficial_visitante = EXCLUDED.placar_oficial_visitante, 
                         local = EXCLUDED.local, partida_data = EXCLUDED.partida_data, 
                         valida = EXCLUDED.valida, timestamp = EXCLUDED.timestamp
        ''', (partida['partida_id'], rodada, partida['clube_casa_id'], partida['clube_visitante_id'],
              partida['placar_oficial_mandante'], partida['placar_oficial_visitante'], partida['local'],
              partida['partida_data'], partida['valida'], partida['timestamp']))
    conn.commit()