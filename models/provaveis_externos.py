"""Sincronização dos prováveis publicados pelo Prováveis do Cartola.

O site externo usa IDs próprios. A tabela guarda o registro bruto, o vínculo
encontrado no nosso ``acf_atletas`` e o método/confiança do mapeamento.
Registros não mapeados permanecem para revisão e não entram automaticamente
nos cálculos.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from bs4 import BeautifulSoup
from psycopg2.extras import Json, execute_values

SOURCE = "provaveisdocartola"
DEFAULT_URL = "https://provaveisdocartola.com.br/"

POSITION_BY_SLOT = {
    "GOL": 1, "LAT-L": 2, "LAT-R": 2, "ZAG-L": 3, "ZAG-R": 3,
    "ZAG-C": 3, "MEI-L": 4, "MEI-R": 4, "MEI-C": 4, "ATA-L": 5,
    "ATA-R": 5, "ATA-C": 5, "TEC": 6,
}


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _site_team_slug(value: str) -> str:
    slug = normalize(value).removesuffix("-v2")
    return slug


def _candidate_keys(row: Dict[str, Any]) -> set[str]:
    return {normalize(row.get("slug")), normalize(row.get("apelido")), normalize(row.get("nome"))} - {""}


def _match_athlete(external_slug: str, external_name: str, club_id: Optional[int], athletes: Iterable[Dict[str, Any]]):
    scoped = [row for row in athletes if club_id is None or row.get("clube_id") == club_id]
    if not scoped:
        return None, 0, "sem_atleta_no_clube"
    slug_key = normalize(external_slug)
    exact_slug = [row for row in scoped if slug_key and normalize(row.get("slug")) == slug_key]
    if len(exact_slug) == 1:
        return exact_slug[0], 1.0, "slug_exato"
    name_key = normalize(external_name)
    exact_name = [row for row in scoped if name_key and name_key in _candidate_keys(row)]
    if len(exact_name) == 1:
        return exact_name[0], 0.98, "nome_exato"
    tokens = {token for token in slug_key.split("-") if len(token) >= 4}
    partial = []
    for row in scoped:
        if tokens and any(tokens.issubset(set(key.split("-"))) for key in _candidate_keys(row)):
            partial.append(row)
    if len(partial) == 1:
        return partial[0], 0.88, "slug_parcial_unico"
    return None, 0, "nao_mapeado"


def _clubs_by_external_slug(cursor):
    cursor.execute("SELECT id, nome, abreviacao, slug, apelido, nome_fantasia FROM acf_clubes")
    clubs = {}
    for row in cursor.fetchall():
        club = {"id": row[0], "nome": row[1], "abreviacao": row[2], "slug": row[3], "apelido": row[4], "nome_fantasia": row[5]}
        for value in (club["slug"], club["nome"], club["apelido"], club["nome_fantasia"], club["abreviacao"]):
            key = normalize(value).removesuffix("-v2")
            if key:
                clubs[key] = club
    return clubs


def sync_html(conn, html: str, temporada: int, rodada: int, captured_at: Optional[datetime] = None) -> Dict[str, int]:
    soup = BeautifulSoup(html, "lxml")
    cursor = conn.cursor()
    clubs = _clubs_by_external_slug(cursor)
    cursor.execute("SELECT atleta_id, clube_id, slug, apelido, nome FROM acf_atletas WHERE temporada = %s", (temporada,))
    athletes = [{"atleta_id": row[0], "clube_id": row[1], "slug": row[2], "apelido": row[3], "nome": row[4]} for row in cursor.fetchall()]

    rows = []
    teams_seen = set()
    for pitch in soup.select(".pitch[data-team]"):
        external_team = pitch.get("data-team", "")
        team_slug = _site_team_slug(external_team)
        club = clubs.get(team_slug)
        if club:
            teams_seen.add(club["id"])
        for figure in pitch.select("figure.player[data-id]"):
            slot = (figure.get("data-slot") or "").upper()
            image = figure.find("img")
            caption = figure.find("figcaption")
            status_raw = normalize(figure.get("data-sit") or "")
            if not status_raw:
                status_raw = "duvida" if "duvida" in (figure.get("class") or []) else "provavel"
            status = {
                "provavel": "provavel", "ok": "provavel", "provaveis": "provavel",
                "duvida": "duvida", "doubt": "duvida", "improvavel": "improvavel",
                "suspenso": "suspenso", "lesionado": "lesionado", "fora": "fora",
            }.get(status_raw, status_raw or "duvida")
            external_name = (caption.get_text(" ", strip=True) if caption else "") or (image.get("alt", "") if image else "")
            external_slug = figure.get("data-slug") or ""
            # O vínculo oficial é deliberadamente manual. O site externo tem
            # nomes/IDs próprios e nenhum palpite automático será ativado nos
            # cálculos; a tela administrativa grava a associação validada.
            athlete, confidence, method = None, 0, "aguarda_mapeamento_manual"
            raw = {"team": external_team, "slot": slot, "name": external_name, "slug": external_slug, "status": status_raw, "photo": image.get("data-photo") if image else None}
            rows.append((temporada, rodada, SOURCE, str(figure.get("data-id")), external_name, external_slug, club["id"] if club else None, team_slug, POSITION_BY_SLOT.get(slot), athlete["atleta_id"] if athlete else None, status, confidence, method, Json(raw), True))

    if not rows:
        raise ValueError("nenhum jogador encontrado no HTML externo")
    now = captured_at or datetime.now(timezone.utc)
    cursor.execute("UPDATE acf_provaveis_fontes SET ativo = FALSE WHERE temporada = %s AND rodada_id = %s AND fonte = %s", (temporada, rodada, SOURCE))
    execute_values(cursor, """
        INSERT INTO acf_provaveis_fontes (temporada, rodada_id, fonte, atleta_externo_id, nome_externo, slug_externo, clube_id, clube_slug_externo, posicao_id, atleta_id, status, confianca_mapeamento, metodo_mapeamento, dados_brutos, ativo, capturado_em)
        VALUES %s
        ON CONFLICT (temporada, rodada_id, fonte, atleta_externo_id) DO UPDATE SET
            nome_externo = EXCLUDED.nome_externo, slug_externo = EXCLUDED.slug_externo,
            clube_id = EXCLUDED.clube_id, clube_slug_externo = EXCLUDED.clube_slug_externo,
            posicao_id = EXCLUDED.posicao_id, atleta_id = EXCLUDED.atleta_id,
            status = EXCLUDED.status, confianca_mapeamento = EXCLUDED.confianca_mapeamento,
            metodo_mapeamento = EXCLUDED.metodo_mapeamento, dados_brutos = EXCLUDED.dados_brutos,
            ativo = TRUE, capturado_em = EXCLUDED.capturado_em
        """, [row + (now,) for row in rows], page_size=250)
    conn.commit()
    cursor.close()
    mapped = sum(1 for row in rows if row[9] is not None)
    return {"registros": len(rows), "clubes": len(teams_seen), "mapeados": mapped, "nao_mapeados": len(rows) - mapped}
