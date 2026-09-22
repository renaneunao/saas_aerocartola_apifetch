"""Sincronização dos prováveis publicados pelo Prováveis do Cartola.

O site externo usa IDs próprios. Registros e clubes são guardados sem vínculo
com entidades oficiais. O administrador valida manualmente os dois níveis.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
from psycopg2.extras import Json, execute_values

SOURCE = "provaveisdocartola"
DEFAULT_URL = "https://provaveisdocartola.com.br/"

POSITION_BY_SLOT = {
    "GOL": 1, "LAT-L": 2, "LAT-R": 2, "ZAG-L": 3, "ZAG-R": 3,
    "ZAG-C": 3, "MEI-L": 4, "MEI-R": 4, "MEI-C": 4, "VOL": 4, "ATA-L": 5,
    "ATA-R": 5, "ATA-C": 5, "TEC": 6,
}


def normalize(value: Any) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _site_team_slug(value: str) -> str:
    slug = normalize(value).removesuffix("-v2")
    return slug


def sync_html(conn, html: str, temporada: int, rodada: int, captured_at: Optional[datetime] = None) -> Dict[str, int]:
    soup = BeautifulSoup(html, "lxml")
    cursor = conn.cursor()
    rows = []
    teams_seen = set()
    for pitch in soup.select(".pitch[data-team]"):
        external_team = pitch.get("data-team", "")
        team_slug = _site_team_slug(external_team)
        if team_slug:
            teams_seen.add(team_slug)
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
            # nomes/IDs próprios e nenhum palpite automático entra no cálculo.
            method = "aguarda_mapeamento_manual"
            raw = {"team": external_team, "slot": slot, "name": external_name, "slug": external_slug, "status": status_raw, "photo": image.get("data-photo") if image else None}
            # Nem os clubes são presumidos: o painel mantém um vínculo manual
            # entre este slug externo e um clube oficial antes de mapear atletas.
            rows.append((temporada, rodada, SOURCE, str(figure.get("data-id")), external_name, external_slug, None, team_slug, POSITION_BY_SLOT.get(slot), None, status, method, Json(raw), True))

    if not rows:
        raise ValueError("nenhum jogador encontrado no HTML externo")
    now = captured_at or datetime.now(timezone.utc)
    cursor.execute("UPDATE acf_provaveis_fontes SET ativo = FALSE WHERE temporada = %s AND rodada_id = %s AND fonte = %s", (temporada, rodada, SOURCE))
    execute_values(cursor, """
        INSERT INTO acf_provaveis_fontes (temporada, rodada_id, fonte, atleta_externo_id, nome_externo, slug_externo, clube_id, clube_slug_externo, posicao_id, atleta_id, status, metodo_mapeamento, dados_brutos, ativo, capturado_em)
        VALUES %s
        ON CONFLICT (temporada, rodada_id, fonte, atleta_externo_id) DO UPDATE SET
            nome_externo = EXCLUDED.nome_externo, slug_externo = EXCLUDED.slug_externo,
            clube_id = EXCLUDED.clube_id, clube_slug_externo = EXCLUDED.clube_slug_externo,
            posicao_id = EXCLUDED.posicao_id, atleta_id = EXCLUDED.atleta_id,
            status = EXCLUDED.status,
            metodo_mapeamento = EXCLUDED.metodo_mapeamento, dados_brutos = EXCLUDED.dados_brutos,
            ativo = TRUE, capturado_em = EXCLUDED.capturado_em
        """, [row + (now,) for row in rows], page_size=250)
    conn.commit()
    cursor.close()
    return {"registros": len(rows), "clubes": len(teams_seen), "mapeados": 0, "nao_mapeados": len(rows)}
