import unittest
from unittest.mock import patch

from models import provaveis_externos


class _Cursor:
    def execute(self, *_args):
        pass

    def close(self):
        pass


class _Connection:
    def __init__(self):
        self.committed = False

    def cursor(self):
        return _Cursor()

    def commit(self):
        self.committed = True


def _figure(alt_cap=""):
    alternate = f'<div class="alt-cap">{alt_cap}</div>' if alt_cap else ""
    return f'''
        <div class="pitch" data-team="athletico-pr_v2">
          <figure class="player jogador ok" data-id="143193" data-slot="ATA-C"
                  data-slug="viveros" data-sit="provavel">
            <img alt="Viveros" data-photo="https://example.test/viveros.webp">
            <figcaption class="cap">Viveros</figcaption>
            {alternate}
          </figure>
        </div>
    '''


class ExternalProbablesParserTests(unittest.TestCase):
    def _parse(self, html):
        conn = _Connection()
        captured = {}

        def capture_values(_cursor, _query, rows, **_kwargs):
            captured["rows"] = rows

        with patch.object(provaveis_externos, "execute_values", side_effect=capture_values):
            result = provaveis_externos.sync_html(conn, html, temporada=2026, rodada=29)

        self.assertTrue(conn.committed)
        self.assertEqual(result["registros"], 1)
        return captured["rows"][0]

    def test_alt_cap_marks_declared_probable_as_doubt(self):
        row = self._parse(_figure("Vargas"))

        self.assertEqual(row[10], "duvida")
        raw = row[12].adapted
        self.assertEqual(raw["status"], "provavel")
        self.assertEqual(raw["status_declarado"], "provavel")
        self.assertEqual(raw["status_calculado"], "duvida")
        self.assertEqual(raw["alt_cap"], "Vargas")

    def test_probable_without_alt_cap_remains_probable(self):
        row = self._parse(_figure())

        self.assertEqual(row[10], "provavel")
        self.assertIsNone(row[12].adapted["alt_cap"])

    def test_public_lineups_json_uses_doubt_and_alternate_id(self):
        conn = _Connection()
        captured = {}

        def capture_values(_cursor, _query, rows, **_kwargs):
            captured["rows"] = rows

        payload = {
            "version": 3845,
            "teams": {
                "athletico-pr_v2": {
                    "titulares": [{
                        "id": 143193,
                        "slot": "ATA-C",
                        "sit": "duvida",
                        "duvida_com": 127871,
                    }]
                }
            },
        }
        market = [
            {"atleta_id": 143193, "apelido_abreviado": "Viveros", "foto": "viveros.webp"},
            {"atleta_id": 127871, "apelido_abreviado": "Vargas"},
        ]

        with patch.object(provaveis_externos, "execute_values", side_effect=capture_values):
            result = provaveis_externos.sync_json(conn, payload, market, temporada=2026, rodada=29)

        self.assertTrue(conn.committed)
        self.assertEqual(result["registros"], 1)
        row = captured["rows"][0]
        self.assertEqual(row[4], "Viveros")
        self.assertEqual(row[10], "duvida")
        self.assertEqual(row[12].adapted["alt_cap"], "Vargas")
        self.assertEqual(row[12].adapted["duvida_com"], 127871)

    def test_duplicate_external_id_uses_market_club_roster(self):
        conn = _Connection()
        captured = {}

        def capture_values(_cursor, _query, rows, **_kwargs):
            captured["rows"] = rows

        alpha = [{"id": 900, "slot": "MEI-C", "sit": "provavel"}]
        alpha += [{"id": athlete_id, "slot": "MEI-C", "sit": "provavel"} for athlete_id in range(100, 106)]
        beta = [{"id": 900, "slot": "MEI-C", "sit": "duvida", "duvida_com": 901}]
        beta += [{"id": athlete_id, "slot": "MEI-C", "sit": "provavel"} for athlete_id in range(200, 206)]
        payload = {"teams": {"alpha_v2": {"titulares": alpha}, "beta_v2": {"titulares": beta}}}
        market = (
            [{"atleta_id": athlete_id, "apelido_abreviado": f"Alpha {athlete_id}", "clube_id": 10}
             for athlete_id in range(100, 106)]
            + [{"atleta_id": athlete_id, "apelido_abreviado": f"Beta {athlete_id}", "clube_id": 20}
               for athlete_id in range(200, 206)]
            + [{"atleta_id": 900, "apelido_abreviado": "Duplicado", "clube_id": 20}]
        )

        with patch.object(provaveis_externos, "execute_values", side_effect=capture_values):
            result = provaveis_externos.sync_json(conn, payload, market, temporada=2026, rodada=29)

        rows = captured["rows"]
        duplicate_row = next(row for row in rows if row[3] == "900")
        self.assertEqual(duplicate_row[7], "beta")
        self.assertEqual(duplicate_row[10], "duvida")
        self.assertEqual(len({row[3] for row in rows}), len(rows))
        self.assertEqual(result["duplicatas_resolvidas"], 1)
        self.assertEqual(result["duplicatas_ignoradas"], 0)


if __name__ == "__main__":
    unittest.main()
