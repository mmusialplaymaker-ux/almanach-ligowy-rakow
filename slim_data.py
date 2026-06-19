#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slim_data.py — przygotowuje "bazowe" pliki dla aplikacji Almanach ligowy.

Co robi:
  1) wczytuje PEŁNY eksport z SQL (stats + matches),
  2) liczy PM Index dokładnie tak jak aplikacja (app.build),
  3) wybiera TOP-N zawodników po PM Index,
  4) zostawia mecze tylko tych zawodników,
  5) przycina kolumny do tych, których aplikacja faktycznie używa,
  6) zapisuje stats_test.csv / matches_test.csv gotowe do uruchomienia i wypchnięcia.

Dzięki temu te SAME dwa pliki dają identyczny wynik lokalnie i na Streamlit Cloud.

Użycie (domyślnie):
  python slim_data.py --stats full_stats.csv --matches full_matches.csv --top 10000

Uwaga: domyślnie NADPISUJE stats_test.csv / matches_test.csv w bieżącym folderze
(to pliki, które czyta aplikacja). Pełny eksport trzymaj pod inną nazwą (full_*).
"""
import argparse
import os
import sys
import types

# --- stub streamlit, żeby dało się policzyć app.build poza uruchomionym Streamlitem ---
_st = types.ModuleType("streamlit")
def _cache_data(*a, **k):
    if a and callable(a[0]):
        return a[0]
    def deco(f):
        return f
    return deco
_st.cache_data = _cache_data
_st.secrets = {}
sys.modules.setdefault("streamlit", _st)

import pandas as pd  # noqa: E402
import app           # noqa: E402  (app.py musi być w tym samym folderze)

# Kolumny faktycznie używane przez aplikację (reszta jest zbędna i tylko waży).
MATCH_KEEP = [
    "player_id", "match_id", "play_id", "league_id", "team_id", "club_id", "opponent_id",
    "team_name", "club_name", "opponent_name", "league_name", "play_name", "region_name",
    "match_date", "minutes", "goals", "yellow_cards", "red_cards", "match_result",
    "team_side", "match_score", "age_at_match", "status_seniorski", "in_selected_play",
]
STATS_KEEP = [
    "player_id", "firstname", "lastname", "team_id", "club_id", "team_name", "club_name",
    "league_name", "play_name", "region_name", "est_birth_year", "status_seniorski",
    "senior_minutes", "senior_squad_apps", "gra_ze_starszymi", "roczniki_w_gore",
    "in_selected_play",
]


def rd_raw(path):
    """Surowe wczytanie 1:1 (tekst), wiele kodowań — bez psucia wartości."""
    for enc in ("utf-8", "cp1250", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python",
                               dtype=str, keep_default_na=False)
        except Exception:
            continue
    raise RuntimeError(f"Nie udało się wczytać {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default="full_stats.csv", help="pełny eksport stats z SQL")
    ap.add_argument("--matches", default="full_matches.csv", help="pełny eksport matches z SQL")
    ap.add_argument("--teamy", default="teamy_kluby_25_26.csv")
    ap.add_argument("--top", type=int, default=10000, help="ilu najlepszych zawodników zostawić")
    ap.add_argument("--out-stats", default="stats_test.csv")
    ap.add_argument("--out-matches", default="matches_test.csv")
    a = ap.parse_args()

    print(f"Wczytuję pełne dane: {a.stats} + {a.matches}")
    stats, matches = app.load_data(a.stats, a.matches, a.teamy)
    print(f"  stats {stats.shape}, matches {matches.shape}")

    print("Liczę PM Index na pełnym zbiorze…")
    d = app.build(stats, matches).sort_values("PM_Index", ascending=False).reset_index(drop=True)
    n = min(a.top, len(d))
    top_ids = set(d.head(n)["player_id"])
    print(f"  graczy ogółem: {len(d)} | wybrano top {n}")
    print(f"  rozkład województw w top: {d.head(n)['region_name'].value_counts().to_dict()}")

    sr, mr = rd_raw(a.stats), rd_raw(a.matches)
    ss = sr[sr["player_id"].isin(top_ids)][[c for c in STATS_KEEP if c in sr.columns]]
    ms = mr[mr["player_id"].isin(top_ids)][[c for c in MATCH_KEEP if c in mr.columns]]
    ss.to_csv(a.out_stats, index=False, encoding="utf-8")
    ms.to_csv(a.out_matches, index=False, encoding="utf-8")

    for f, rows in [(a.out_stats, len(ss)), (a.out_matches, len(ms))]:
        print(f"  zapisano {f}: {round(os.path.getsize(f)/1e6, 1)} MB | {rows} wierszy")

    # kontrola: czy top po odchudzeniu pokrywa się z topem na pełnym zbiorze
    s2, m2 = app.load_data(a.out_stats, a.out_matches, a.teamy)
    d2 = app.build(s2, m2).sort_values("PM_Index", ascending=False).reset_index(drop=True)
    for k in (15, 50, 100):
        full_top = list(d.head(k)["player_id"])
        slim_top = set(d2.head(k)["player_id"])
        overlap = sum(1 for p in full_top if p in slim_top)
        print(f"  pokrycie TOP{k}: {overlap}/{k}")
    print("Gotowe. Użyj tych plików lokalnie I wypchnij je do repo — wtedy są identyczne.")


if __name__ == "__main__":
    main()
