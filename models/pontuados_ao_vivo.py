"""Persist the latest complete athlete-points feed for each season/round."""
from datetime import datetime, timezone
import math

from psycopg2.extras import Json, execute_values


def _athletes(payload):
    athletes = payload.get('atletas') if isinstance(payload, dict) else None
    if isinstance(athletes, list):
        return [(item.get('atleta_id', item.get('id')), item) for item in athletes
                if isinstance(item, dict)]
    if isinstance(athletes, dict):
        return [(item.get('atleta_id', item.get('id', key)), item)
                for key, item in athletes.items() if isinstance(item, dict)]
    return []


def update_pontuados_ao_vivo(conn, payload, round_number, season):
    """Atomically replace stale rows with one validated global live snapshot.

    A score of ``0`` is persisted only when Cartola explicitly publishes it;
    missing/invalid scores remain SQL NULL. An empty or mismatched feed is
    rejected without touching the last known snapshot.
    """
    if (not isinstance(payload, dict)
            or str(payload.get('rodada')) != str(round_number)
            or type(round_number) is not int or round_number < 1
            or type(season) is not int or season < 1):
        return False

    source = _athletes(payload)
    rows = []
    for raw_id, athlete in source:
        try:
            athlete_id = int(raw_id)
        except (TypeError, ValueError, OverflowError):
            continue
        if athlete_id <= 0:
            continue
        score = athlete.get('pontuacao')
        if type(score) not in (int, float) or not math.isfinite(float(score)):
            score = None
        entered = athlete.get('entrou_em_campo')
        if not isinstance(entered, bool):
            entered = None
        club_id = athlete.get('clube_id')
        position_id = athlete.get('posicao_id')
        try:
            club_id = int(club_id) if club_id is not None else None
        except (TypeError, ValueError, OverflowError):
            club_id = None
        try:
            position_id = int(position_id) if position_id is not None else None
        except (TypeError, ValueError, OverflowError):
            position_id = None
        scouts = athlete.get('scout')
        rows.append((season, round_number, athlete_id, club_id, position_id, score,
                     entered, athlete.get('apelido'), athlete.get('foto'),
                     Json(scouts if isinstance(scouts, dict) else {})))

    if not rows:
        return False

    snapshot_at = datetime.now(timezone.utc)
    cursor = conn.cursor()
    try:
        # Both the scoped delete and inserts commit together, so readers never
        # observe a mixture of two feed generations.
        cursor.execute(
            "DELETE FROM acf_pontuados_ao_vivo "
            "WHERE temporada=%s AND rodada_id=%s AND atleta_id <> ALL(%s)",
            (season, round_number, [row[2] for row in rows]),
        )
        execute_values(cursor, """
            INSERT INTO acf_pontuados_ao_vivo
                (temporada,rodada_id,atleta_id,clube_id,posicao_id,pontuacao,
                 entrou_em_campo,apelido,foto,scout,snapshot_em)
            VALUES %s
            ON CONFLICT (temporada,rodada_id,atleta_id) DO UPDATE SET
                clube_id=EXCLUDED.clube_id,
                posicao_id=EXCLUDED.posicao_id,
                pontuacao=EXCLUDED.pontuacao,
                entrou_em_campo=EXCLUDED.entrou_em_campo,
                apelido=EXCLUDED.apelido,
                foto=EXCLUDED.foto,
                scout=EXCLUDED.scout,
                snapshot_em=EXCLUDED.snapshot_em
        """, [row + (snapshot_at,) for row in rows], page_size=1000)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
    return len(rows)
