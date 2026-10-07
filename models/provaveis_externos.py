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
DEFAULT_LINEUPS_URL = "https://provaveisdocartola.com.br/api/lineups-public"
DEFAULT_MARKET_URL = "https://provaveisdocartola.com.br/assets/data/mercado.images.json"

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


def _canonical_status(value: Any, has_alternate: bool = False) -> str:
    status_raw = normalize(value)
    if has_alternate:
        return "duvida"
    return {
        "provavel": "provavel", "ok": "provavel", "provaveis": "provavel",
        "duvida": "duvida", "doubt": "duvida", "improvavel": "improvavel",
        "suspenso": "suspenso", "lesionado": "lesionado", "fora": "fora",
    }.get(status_raw, status_raw or "duvida")


def _persist_snapshot(conn, rows, teams_seen, temporada, rodada, captured_at):
    if not rows:
        raise ValueError("nenhum jogador encontrado na fonte externa")
    cursor = conn.cursor()
    now = captured_at or datetime.now(timezone.utc)
    cursor.execute(
        "UPDATE acf_provaveis_fontes SET ativo = FALSE "
        "WHERE temporada = %s AND rodada_id = %s AND fonte = %s",
        (temporada, rodada, SOURCE),
    )
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


def sync_json(conn, payload: Dict[str, Any], market: list, temporada: int, rodada: int,
              captured_at: Optional[datetime] = None) -> Dict[str, int]:
    """Sincroniza o JSON que o próprio site usa para renderizar as escalações.

    O HTML inicial não contém os titulares: o navegador os monta a partir de
    ``/api/lineups-public``. Por isso este endpoint, não o DOM renderizado, é a
    fonte autoritativa para ``sit`` e ``duvida_com``.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("teams"), dict):
        raise ValueError("JSON de escalações externas inválido ou sem times")
    if not isinstance(market, list):
        raise ValueError("JSON de atletas externo inválido")

    market_by_id = {
        str(player.get("atleta_id")): player
        for player in market
        if isinstance(player, dict) and player.get("atleta_id") is not None
    }
    candidates_by_id = {}
    teams_seen = set()
    club_votes = {}
    for external_team, team_data in payload["teams"].items():
        if not isinstance(team_data, dict):
            continue
        team_slug = _site_team_slug(external_team)
        if team_slug:
            teams_seen.add(team_slug)
        for player in team_data.get("titulares") or []:
            if not isinstance(player, dict) or player.get("id") is None:
                continue
            external_id = str(player["id"])
            details = market_by_id.get(external_id, {})
            market_club_id = details.get("clube_id")
            if market_club_id is not None and team_slug:
                club_votes.setdefault(str(market_club_id), {}).setdefault(team_slug, 0)
                club_votes[str(market_club_id)][team_slug] += 1
            candidates_by_id.setdefault(external_id, []).append({
                "player": player,
                "team": external_team,
                "team_slug": team_slug,
                "details": details,
            })

    # O lineups-public pode repetir atletas em elencos antigos/incompletos.
    # A tabela tem uma chave por ID externo; para duplicatas, escolhemos apenas
    # a ocorrência que coincide com o clube predominante desse ID no mercado.
    trusted_team_by_club = {}
    for club_id, votes in club_votes.items():
        ranked = sorted(votes.items(), key=lambda item: item[1], reverse=True)
        if ranked and ranked[0][1] >= 6 and (len(ranked) == 1 or ranked[0][1] >= 2 * ranked[1][1]):
            trusted_team_by_club[club_id] = ranked[0][0]

    rows = []
    duplicates_resolved = 0
    duplicates_skipped = 0
    for external_id, candidates in candidates_by_id.items():
        if len(candidates) > 1:
            details = candidates[0]["details"]
            market_club_id = details.get("clube_id")
            expected_team = trusted_team_by_club.get(str(market_club_id)) if market_club_id is not None else None
            candidates = [candidate for candidate in candidates if candidate["team_slug"] == expected_team]
            if len(candidates) != 1:
                duplicates_skipped += 1
                continue
            duplicates_resolved += 1

        candidate = candidates[0]
        player = candidate["player"]
        external_team = candidate["team"]
        team_slug = candidate["team_slug"]
        details = candidate["details"]
        slot = str(player.get("slot") or "").upper()
        alternate_id = player.get("duvida_com")
        alternate = market_by_id.get(str(alternate_id), {}) if alternate_id is not None else {}
        declared_status = _canonical_status(player.get("sit"))
        status = _canonical_status(player.get("sit"), has_alternate=alternate_id is not None)
        external_name = (
            details.get("apelido_abreviado") or details.get("apelido")
            or details.get("nome") or external_id
        )
        external_slug = normalize(external_name)
        raw = {
            "team": external_team,
            "slot": slot,
            "name": external_name,
            "slug": external_slug,
            "status": normalize(player.get("sit")),
            "status_declarado": declared_status,
            "status_calculado": status,
            "duvida_com": alternate_id,
            "alt_cap": (
                alternate.get("apelido_abreviado") or alternate.get("apelido")
                or alternate.get("nome") or None
            ),
            "photo": details.get("foto"),
            "source": "api/lineups-public",
        }
        rows.append((
            temporada, rodada, SOURCE, external_id, external_name, external_slug,
            None, team_slug, POSITION_BY_SLOT.get(slot), None, status,
            "aguarda_mapeamento_manual", Json(raw), True,
        ))

    summary = _persist_snapshot(conn, rows, teams_seen, temporada, rodada, captured_at)
    summary["duplicatas_resolvidas"] = duplicates_resolved
    summary["duplicatas_ignoradas"] = duplicates_skipped
    return summary


def sync_html(conn, html: str, temporada: int, rodada: int, captured_at: Optional[datetime] = None) -> Dict[str, int]:
    soup = BeautifulSoup(html, "lxml")
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
            alternate = figure.select_one(".alt-cap")
            status_raw = normalize(figure.get("data-sit") or "")
            if not status_raw:
                status_raw = "duvida" if "duvida" in (figure.get("class") or []) else "provavel"
            declared_status = _canonical_status(status_raw)
            # O site pode manter data-sit="provavel" no titular mesmo quando
            # há um substituto em .alt-cap. Nesse layout, o titular é dúvida:
            # a vaga depende da disputa/alternância com o nome indicado ali.
            status = _canonical_status(status_raw, has_alternate=alternate is not None)
            external_name = (caption.get_text(" ", strip=True) if caption else "") or (image.get("alt", "") if image else "")
            external_slug = figure.get("data-slug") or ""
            # O vínculo oficial é deliberadamente manual. O site externo tem
            # nomes/IDs próprios e nenhum palpite automático entra no cálculo.
            method = "aguarda_mapeamento_manual"
            raw = {
                "team": external_team,
                "slot": slot,
                "name": external_name,
                "slug": external_slug,
                "status": status_raw,
                "status_declarado": declared_status,
                "status_calculado": status,
                "alt_cap": alternate.get_text(" ", strip=True) if alternate else None,
                "photo": image.get("data-photo") if image else None,
            }
            # Nem os clubes são presumidos: o painel mantém um vínculo manual
            # entre este slug externo e um clube oficial antes de mapear atletas.
            rows.append((temporada, rodada, SOURCE, str(figure.get("data-id")), external_name, external_slug, None, team_slug, POSITION_BY_SLOT.get(slot), None, status, method, Json(raw), True))

    return _persist_snapshot(conn, rows, teams_seen, temporada, rodada, captured_at)
