def create_clubes_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clubes (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            abreviacao TEXT,
            slug TEXT,
            apelido TEXT,
            nome_fantasia TEXT,
            url_editoria TEXT
        )
    ''')
    conn.commit()

def update_clubes(conn, clubes_data):
    cursor = conn.cursor()
    for clube_id, clube in clubes_data.items():
        cursor.execute('''
            INSERT INTO clubes (id, nome, abreviacao, slug, apelido, nome_fantasia, url_editoria)
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