import unittest
from unittest.mock import patch

from models.pontuados_ao_vivo import update_pontuados_ao_vivo


class _Cursor:
    def __init__(self):
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class LivePointsStoreTests(unittest.TestCase):
    def test_persists_explicit_zero_without_turning_missing_points_into_zero(self):
        conn = _Connection()
        payload = {"rodada": 35, "atletas": {
            "101": {"pontuacao": 0.0, "entrou_em_campo": False, "scout": {}},
            "102": {"entrou_em_campo": None, "scout": {"DS": 1}},
        }}
        with patch("models.pontuados_ao_vivo.execute_values") as execute_values:
            inserted = update_pontuados_ao_vivo(conn, payload, 35, 2026)

        self.assertEqual(inserted, 2)
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertIn("DELETE FROM acf_pontuados_ao_vivo", conn.cursor_instance.executed[0][0])
        rows = execute_values.call_args.args[2]
        self.assertEqual(rows[0][5], 0.0)
        self.assertIsNone(rows[1][5])
        self.assertEqual(rows[0][1:3], (35, 101))

    def test_empty_or_wrong_round_payload_preserves_last_snapshot(self):
        for payload in (
            {"rodada": 35, "atletas": {}},
            {"rodada": 34, "atletas": {"101": {"pontuacao": 1.0}}},
        ):
            conn = _Connection()
            with self.subTest(payload=payload), \
                 patch("models.pontuados_ao_vivo.execute_values") as execute_values:
                self.assertFalse(update_pontuados_ao_vivo(conn, payload, 35, 2026))
                execute_values.assert_not_called()
                self.assertEqual(conn.cursor_instance.executed, [])
                self.assertEqual(conn.commits, 0)


if __name__ == "__main__":
    unittest.main()
