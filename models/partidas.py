def update_partidas(conn, partidas_data, rodada):
    """
    Atualiza partidas de uma rodada.
    Usa ON CONFLICT DO UPDATE para atualizar partidas existentes (ex: placares) 
    e inserir novas se necessário.
    O controle de "já atualizado" é feito no data_fetcher.py.
    """
    cursor = conn.cursor()
    
    if not partidas_data or 'partidas' not in partidas_data:
        print(f"Nenhuma partida fornecida para rodada {rodada}")
        return
    
    for partida in partidas_data['partidas']:
        cursor.execute('''
            INSERT INTO acf_partidas (partida_id, rodada_id, clube_casa_id, clube_visitante_id, 
                                            placar_oficial_mandante, placar_oficial_visitante, local, 
                                            partida_data, valida, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (partida_id) 
            DO UPDATE SET rodada_id = EXCLUDED.rodada_id, 
                         clube_casa_id = EXCLUDED.clube_casa_id, 
                         clube_visitante_id = EXCLUDED.clube_visitante_id, 
                         placar_oficial_mandante = EXCLUDED.placar_oficial_mandante, 
                         placar_oficial_visitante = EXCLUDED.placar_oficial_visitante, 
                         local = EXCLUDED.local, 
                         partida_data = EXCLUDED.partida_data, 
                         valida = EXCLUDED.valida, 
                         timestamp = EXCLUDED.timestamp
        ''', (partida['partida_id'], rodada, partida['clube_casa_id'], partida['clube_visitante_id'],
              partida['placar_oficial_mandante'], partida['placar_oficial_visitante'], partida['local'],
              partida['partida_data'], partida['valida'], partida['timestamp']))
    
    conn.commit()
    print(f"Partidas da rodada {rodada} atualizadas: {len(partidas_data['partidas'])} partidas")