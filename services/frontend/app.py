"""TyperCloud - frontend (Streamlit).

Obsluguje logowanie OAuth2 PKCE oraz widoki: mecze, typowanie, ranking,
a dla ADMINA dodatkowo zarzadzanie meczami i wpisywanie wynikow.
"""
import base64
import os
from functools import lru_cache

import httpx
import streamlit as st

import auth

API_URL = os.environ.get("API_URL", "http://localhost:8000")
ICON_PATH = os.path.join(os.path.dirname(__file__), "img", "iconTyper.png")


@lru_cache
def icon_data_uri():
    """Wczytuje ikone jako data-URI (base64). Zwraca None, gdy pliku brak."""
    try:
        with open(ICON_PATH, "rb") as fh:
            encoded = base64.b64encode(fh.read()).decode()
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return None

st.set_page_config(page_title="TyperCloud", page_icon="⚽", layout="centered")

# Motyw fioletowo-czarno-szary + stylizacja kart i sidebaru.
_CSS = """
<style>
.stApp { background: radial-gradient(1200px 600px at 50% -10%, #221b33 0%, #15131c 60%); }
section[data-testid="stSidebar"] { background: #1b1726; border-right: 1px solid #2e2740; }
h1, h2, h3 { color: #c9b8ff !important; letter-spacing: .3px; }
.tc-hero {
  background: linear-gradient(135deg, #6d28d9 0%, #3b1f6b 60%, #1f1830 100%);
  padding: 22px 26px; border-radius: 16px; margin-bottom: 18px;
  border: 1px solid #4c3a7a; box-shadow: 0 8px 30px rgba(109,40,217,.25);
}
.tc-hero h1 { margin: 0; color: #fff !important; font-size: 1.9rem; }
.tc-hero p { margin: 4px 0 0; color: #d9ccff; opacity: .9; }
.tc-card {
  background: #241f33; border: 1px solid #34294d; border-left: 4px solid #8b5cf6;
  border-radius: 12px; padding: 12px 16px; margin-bottom: 10px;
  display: flex; justify-content: space-between; align-items: center;
}
.tc-card.finished { border-left-color: #6b7280; opacity: .92; }
.tc-teams { font-size: 1.05rem; font-weight: 600; color: #ece7f7; }
.tc-id { color: #8b80a8; font-size: .8rem; margin-right: 8px; }
.tc-score { font-size: 1.25rem; font-weight: 800; color: #a78bfa; }
.tc-pending { color: #8b80a8; font-size: .9rem; font-style: italic; }
.tc-badge {
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: .72rem; font-weight: 700; letter-spacing: .4px;
}
.tc-badge.user { background: #3b2f5c; color: #c9b8ff; }
.tc-badge.admin { background: #6d28d9; color: #fff; }
.tc-badge.none { background: #2e2740; color: #8b80a8; }
div[data-testid="stMetric"] {
  background: #241f33; border: 1px solid #34294d; border-radius: 12px; padding: 10px 14px;
}
.stButton button, .stLinkButton a, .stFormSubmitButton button {
  background: linear-gradient(135deg, #7c3aed, #6d28d9) !important; color: #fff !important;
  border: 0 !important; border-radius: 10px !important; font-weight: 600 !important;
}
.tc-loginbtn {
  display: inline-block; width: 100%; box-sizing: border-box; text-align: center;
  padding: 12px 18px; border-radius: 10px; text-decoration: none; font-weight: 600;
  background: linear-gradient(135deg, #7c3aed, #6d28d9); color: #fff !important;
  box-shadow: 0 6px 20px rgba(124,58,237,.35);
}
.tc-loginbtn:hover { filter: brightness(1.08); }
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def api_get(path: str, token: str):
    resp = httpx.get(
        f"{API_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, token: str, payload: dict):
    resp = httpx.post(
        f"{API_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def api_put(path: str, token: str, payload: dict):
    resp = httpx.put(
        f"{API_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def api_delete(path: str, token: str):
    resp = httpx.delete(
        f"{API_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    resp.raise_for_status()


def handle_login_callback():
    """Po powrocie z Zitadel zamienia 'code' na token."""
    params = st.query_params
    if "code" in params and "access_token" not in st.session_state:
        code = params["code"]
        state = params.get("state", "")
        verifier = auth.pop_verifier(state)
        if not verifier:
            # Brak verifiera (np. odswiezenie callbacku) - wroc do czystego logowania.
            st.query_params.clear()
            st.rerun()
            return
        try:
            token_data = auth.exchange_code_for_token(code, verifier)
            access_token = token_data["access_token"]
            userinfo = auth.get_userinfo(access_token)
        except httpx.HTTPError as exc:
            # Zapisujemy blad, by render_login NIE wpadl w petle auto-przekierowania.
            st.session_state["auth_error"] = str(exc)
            st.query_params.clear()
            return
        st.session_state.pop("auth_error", None)
        st.session_state["access_token"] = access_token
        # id_token sluzy jako hint przy wylogowaniu (OIDC End Session).
        st.session_state["id_token"] = token_data.get("id_token")
        st.session_state["claims"] = userinfo
        st.session_state["username"] = userinfo.get("preferred_username") or userinfo.get(
            "email", "uzytkownik"
        )
        st.session_state["roles"] = auth.extract_roles(userinfo)
        st.query_params.clear()
        st.rerun()


def render_login():
    icon = icon_data_uri()
    logo = (
        f'<img src="{icon}" alt="TyperCloud logo" '
        'style="width:120px;margin-bottom:12px;border-radius:22px">'
        if icon
        else "<h1>TyperCloud</h1>"
    )
    st.markdown(
        f'<div class="tc-hero" style="text-align:center;">{logo}'
        "<p>Typuj wyniki meczow pilkarskich. Zaloguj sie przez Zitadel ",
        unsafe_allow_html=True,
    )

    if st.session_state.get("auth_error"):
        st.error(f"Logowanie nie powiodlo sie: {st.session_state['auth_error']}")

    login_url = auth.start_login()
    # Przycisk logowania (ta sama karta). Zitadel wymusza podanie danych za
    # kazdym razem (parametr prompt=login), wiec trzeba sie zalogowac na nowo.
    st.markdown(
        f'<a class="tc-loginbtn" href="{login_url}" target="_self">'
        "Zaloguj sie przez Zitadel</a>",
        unsafe_allow_html=True,
    )


def _match_card(m: dict):
    finished = m["status"] == "finished"
    cls = "tc-card finished" if finished else "tc-card"
    if finished:
        right = f'<span class="tc-score">{m["score_a"]} : {m["score_b"]}</span>'
    else:
        right = '<span class="tc-pending">nadchodzacy</span>'
    st.markdown(
        f'<div class="{cls}"><div class="tc-teams">'
        f'<span class="tc-id">#{m["id"]}</span>{m["team_a"]} vs {m["team_b"]}'
        f"</div>{right}</div>",
        unsafe_allow_html=True,
    )


def render_matches(token: str):
    matches = api_get("/api/matches", token)
    upcoming = [m for m in matches if m["status"] == "scheduled"]
    finished = [m for m in matches if m["status"] == "finished"]

    st.subheader("Nadchodzace mecze")
    if upcoming:
        for m in upcoming:
            _match_card(m)
    else:
        st.caption("Brak nadchodzacych meczow.")

    st.subheader("Rozegrane mecze")
    if finished:
        for m in finished:
            _match_card(m)
    else:
        st.caption("Zaden mecz nie zostal jeszcze rozegrany.")

    return matches


_OUTCOME_MAP = {
    "Wygrana gospodarzy (1)": "home",
    "Remis (X)": "draw",
    "Wygrana gosci (2)": "away",
}


def render_prediction_form(token: str, matches: list):
    st.subheader("Postaw swoj typ")
    open_matches = [m for m in matches if m["status"] == "scheduled"]
    if not open_matches:
        st.caption("Brak meczow otwartych do typowania.")
        return
    labels = {f"#{m['id']} {m['team_a']} vs {m['team_b']}": m["id"] for m in open_matches}

    # Widgety POZA st.form -> zmiana "Rodzaj typu" od razu przelacza pola formularza.
    choice = st.selectbox("Mecz", list(labels.keys()), key="pred_match")
    mode = st.radio(
        "Rodzaj typu",
        ["Dokladny wynik (3 pkt)", "Tylko rezultat 1/X/2 (1 pkt)"],
        horizontal=True,
        key="pred_mode",
    )

    payload = {"match_id": labels[choice]}
    if mode.startswith("Dokladny"):
        col1, col2 = st.columns(2)
        score_a = col1.number_input("Gole gospodarzy", min_value=0, step=1, value=0)
        score_b = col2.number_input("Gole gosci", min_value=0, step=1, value=0)
        payload.update(
            bet_type="score",
            predicted_score_a=int(score_a),
            predicted_score_b=int(score_b),
        )
    else:
        outcome_label = st.radio("Rezultat", list(_OUTCOME_MAP.keys()))
        payload.update(
            bet_type="outcome",
            predicted_outcome=_OUTCOME_MAP[outcome_label],
        )

    if st.button("Wyslij typ", use_container_width=True):
        try:
            api_post("/api/predictions", token, payload)
            st.success("Typ zapisany!")
        except httpx.HTTPStatusError as exc:
            st.error(f"Blad: {exc.response.text}")


def render_rankings(token: str):
    st.subheader("Tabela rankingowa")
    rankings = api_get("/api/rankings", token)
    if not rankings:
        st.caption("Ranking jest jeszcze pusty.")
        return
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    st.table(
        [
            {
                "Miejsce": f"{medals.get(i, '')} {i + 1}".strip(),
                "Gracz": r["username"],
                "Punkty": r["points"],
            }
            for i, r in enumerate(rankings)
        ]
    )


def render_admin(token: str, matches: list):
    st.divider()
    st.subheader("Panel administratora")

    with st.form("add_match_form"):
        st.markdown("**Dodaj nowy mecz**")
        team_a = st.text_input("Gospodarz")
        team_b = st.text_input("Gosc")
        add = st.form_submit_button("Dodaj mecz", use_container_width=True)
    if add and team_a and team_b:
        try:
            api_post("/api/matches", token, {"team_a": team_a, "team_b": team_b})
            st.success("Mecz dodany!")
            st.rerun()
        except httpx.HTTPStatusError as exc:
            st.error(f"Blad: {exc.response.text}")

    scheduled = [m for m in matches if m["status"] == "scheduled"]
    if scheduled:
        with st.form("result_form"):
            st.markdown("**Wpisz wynik meczu** (uruchomi przeliczanie punktow)")
            labels = {
                f"#{m['id']} {m['team_a']} vs {m['team_b']}": m["id"] for m in scheduled
            }
            choice = st.selectbox("Mecz", list(labels.keys()))
            c1, c2 = st.columns(2)
            ra = c1.number_input("Wynik gospodarzy", min_value=0, step=1, value=0)
            rb = c2.number_input("Wynik gosci", min_value=0, step=1, value=0)
            save = st.form_submit_button("Zapisz wynik", use_container_width=True)
        if save:
            try:
                api_put(
                    f"/api/matches/{labels[choice]}/result",
                    token,
                    {"score_a": int(ra), "score_b": int(rb)},
                )
                st.success("Wynik zapisany. Worker przelicza punkty...")
                st.rerun()
            except httpx.HTTPStatusError as exc:
                st.error(f"Blad: {exc.response.text}")

    # Usuwanie meczow (nadchodzacych lub rozegranych).
    if matches:
        with st.form("delete_match_form"):
            st.markdown("**Usun mecz** (nadchodzacy lub rozegrany)")
            del_labels = {
                f"#{m['id']} {m['team_a']} vs {m['team_b']} ({m['status']})": m["id"]
                for m in matches
            }
            del_choice = st.selectbox("Mecz do usuniecia", list(del_labels.keys()))
            remove = st.form_submit_button("Usun mecz", use_container_width=True)
        if remove:
            try:
                api_delete(f"/api/matches/{del_labels[del_choice]}", token)
                st.success("Mecz usuniety.")
                st.rerun()
            except httpx.HTTPStatusError as exc:
                st.error(f"Blad: {exc.response.text}")


def _role_badges(roles: list) -> str:
    if not roles:
        return '<span class="tc-badge none">brak rol</span>'
    out = []
    for r in roles:
        cls = "admin" if r == "ADMIN" else "user" if r == "USER" else "none"
        out.append(f'<span class="tc-badge {cls}">{r}</span>')
    return " ".join(out)


def render_sidebar(token: str, roles: list):
    is_admin = "ADMIN" in roles
    st.sidebar.markdown("### TyperCloud")
    icon = icon_data_uri()
    username = st.session_state.get("username")

    st.sidebar.markdown(f"Uzytkownik: **{username}**")
    st.sidebar.markdown(_role_badges(roles), unsafe_allow_html=True)
    st.sidebar.divider()
    if st.sidebar.button("Wyloguj", use_container_width=True):
        # Czyscimy sesje aplikacji i wracamy na ekran logowania.
        # Ponowne logowanie i tak wymusza podanie danych (prompt=login),
        # wiec nie trzeba przekierowywac do Zitadela (zadnego ekranu "Wylogowanie...").
        st.session_state.clear()
        st.rerun()

    # Tabela debugowa dostepna WYLACZNIE dla roli ADMIN.
    if is_admin:
        st.sidebar.divider()
        with st.sidebar.expander("Debug (ADMIN): token"):
            st.json(st.session_state.get("claims", {}))
            st.caption("Surowy access_token:")
            st.code(token, language="text")


def main():
    inject_css()
    handle_login_callback()

    if "access_token" not in st.session_state:
        render_login()
        return

    token = st.session_state["access_token"]
    roles = st.session_state.get("roles", [])

    render_sidebar(token, roles)

    # st.markdown(
    #     '<div class="tc-hero"><h1>⚽ TyperCloud</h1>'
    #     "<p>Twoje typy, wyniki na zywo i ranking graczy.</p></div>",
    #     unsafe_allow_html=True,
    # )
    icon = icon_data_uri()
    logo = (
        f'<img src="{icon}" alt="TyperCloud logo" '
        'style="width:80px;margin-bottom:5px;border-radius:15px">'
        if icon
        else "<h1>TyperCloud</h1>"
    )
    st.markdown(f'<div class="tc-hero" style="text-align:center;">{logo} <p>Twoje typy, wyniki na zywo i ranking graczy.</p></div>', unsafe_allow_html=True)
    try:
        matches = render_matches(token)
        st.divider()
        render_prediction_form(token, matches)
        st.divider()
        render_rankings(token)
        if "ADMIN" in roles:
            render_admin(token, matches)
    except httpx.HTTPStatusError as exc:
        # Pokaz konkretny powod zwrocony przez backend (np. tresc bledu JWT/roli).
        st.error(f"API odrzucilo zadanie ({exc.response.status_code}): {exc.response.text}")
    except httpx.HTTPError as exc:
        st.error(f"Problem z polaczeniem z API: {exc}")


if __name__ == "__main__":
    main()
