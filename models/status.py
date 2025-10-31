def update_status(conn, status_data):
    cursor = conn.cursor()
    for status_id, status in status_data.items():
        cursor.execute('''
            INSERT INTO status (id, nome)
            VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET
                nome = EXCLUDED.nome
        ''', (int(status_id), status['nome']))
    conn.commit()