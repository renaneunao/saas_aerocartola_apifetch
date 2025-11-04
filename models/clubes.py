def update_clubes(conn, clubes_data):
    cursor = conn.cursor()
    for clube_id, clube in clubes_data.items():
        cursor.execute('''
            INSERT INTO acf_clubes (id, nome, abreviacao, slug, apelido, nome_fantasia, url_editoria)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                nome = EXCLUDED.nome,
                abreviacao = EXCLUDED.abreviacao,
                slug = EXCLUDED.slug,
                apelido = EXCLUDED.apelido,
                nome_fantasia = EXCLUDED.nome_fantasia,
                url_editoria = EXCLUDED.url_editoria
        ''', (int(clube_id), clube['nome'], clube['abreviacao'], clube['slug'], clube['apelido'], clube['nome_fantasia'], clube['url_editoria']))
    conn.commit()