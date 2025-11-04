def update_esquemas(conn, esquemas_data):
    cursor = conn.cursor()
    for esquema in esquemas_data:
        cursor.execute('''
            INSERT INTO acf_esquemas (esquema_id, nome, ata, gol, lat, mei, tec, zag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (esquema_id) DO UPDATE SET
                nome = EXCLUDED.nome,
                ata = EXCLUDED.ata,
                gol = EXCLUDED.gol,
                lat = EXCLUDED.lat,
                mei = EXCLUDED.mei,
                tec = EXCLUDED.tec,
                zag = EXCLUDED.zag
        ''', (esquema['esquema_id'], esquema['nome'], esquema['posicoes']['ata'], esquema['posicoes']['gol'],
              esquema['posicoes']['lat'], esquema['posicoes']['mei'], esquema['posicoes']['tec'], esquema['posicoes']['zag']))
    conn.commit()