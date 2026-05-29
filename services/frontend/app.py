"""TyperCloud - frontend (Streamlit).

Obsluguje logowanie OAuth2 PKCE oraz widoki: mecze, typowanie, ranking,
a dla ADMINA dodatkowo zarzadzanie meczami i wpisywanie wynikow.
"""
import os

import httpx
import streamlit as st

import auth

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="TyperCloud", page_icon="football", layout="centered")


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


def handle_login_callback():
    """Po powrocie z Zitadel zamienia 'code' na token."""
    params = st.query_params
    if "code" in params and "access_token" not in st.session_state:
        code = params["code"]
        state = params.get("state", "")
        verifier = auth.pop_verifier(state)
        if not verifier:
            st.error("Sesja logowania wygasla - kliknij 'Zaloguj sie' jeszcze raz.")
            return
        try:
            token_data = auth.exchange_code_for_token(code, verifier)
        except httpx.HTTPError as exc:
            st.error(f"Nie udalo sie pobrac tokenu: {exc}")
            return
        access_token = token_data["access_token"]
        st.session_state["access_token"] = access_token
        # Role i nazwe uzytkownika bierzemy z userinfo (access token ich nie zawiera).
        try:
            userinfo = auth.get_userinfo(access_token)
        except httpx.HTTPError as exc:
            st.error(f"Nie udalo sie pobrac userinfo: {exc}")
            return
        st.session_state["claims"] = userinfo
        st.session_state["username"] = userinfo.get("preferred_username") or userinfo.get(
            "email", "uzytkownik"
        )
        st.session_state["roles"] = auth.extract_roles(userinfo)
        st.query_params.clear()
        st.rerun()


def render_login():
    st.title("TyperCloud - Typer Pilkarski")
    st.write("Zaloguj sie przez Zitadel (OAuth 2.0 + PKCE), aby typowac wyniki.")
    login_url = auth.start_login()
    st.link_button("Zaloguj sie przez Zitadel", login_url)


def render_matches(token: str):
    st.subheader("Nadchodzace i rozegrane mecze")
    matches = api_get("/api/matches", token)
    if not matches:
        st.info("Brak meczow. Poczekaj, az administrator je doda.")
        return matches
    for m in matches:
        result = (
            f"{m['score_a']} : {m['score_b']}"
            if m["status"] == "finished"
            else "-- : --"
        )
        st.write(
            f"#{m['id']}  **{m['team_a']}** vs **{m['team_b']}**  "
            f"({m['status']}) wynik: {result}"
        )
    return matches


def render_prediction_form(token: str, matches: list):
    st.subheader("Postaw swoj typ")
    open_matches = [m for m in matches if m["status"] == "scheduled"]
    if not open_matches:
        st.info("Brak meczow otwartych do typowania.")
        return
    labels = {f"#{m['id']} {m['team_a']} vs {m['team_b']}": m["id"] for m in open_matches}
    with st.form("prediction_form"):
        choice = st.selectbox("Mecz", list(labels.keys()))
        col1, col2 = st.columns(2)
        score_a = col1.number_input("Gole gospodarzy", min_value=0, step=1, value=0)
        score_b = col2.number_input("Gole gosci", min_value=0, step=1, value=0)
        submitted = st.form_submit_button("Wyslij typ")
    if submitted:
        try:
            api_post(
                "/api/predictions",
                token,
                {
                    "match_id": labels[choice],
                    "predicted_score_a": int(score_a),
                    "predicted_score_b": int(score_b),
                },
            )
            st.success("Typ zapisany!")
        except httpx.HTTPStatusError as exc:
            st.error(f"Blad: {exc.response.text}")


def render_rankings(token: str):
    st.subheader("Tabela rankingowa")
    rankings = api_get("/api/rankings", token)
    if not rankings:
        st.info("Ranking jest jeszcze pusty.")
        return
    st.table(
        [{"Miejsce": i + 1, "Gracz": r["username"], "Punkty": r["points"]}
         for i, r in enumerate(rankings)]
    )


def render_admin(token: str, matches: list):
    st.divider()
    st.subheader("Panel administratora")

    with st.form("add_match_form"):
        st.write("Dodaj nowy mecz")
        team_a = st.text_input("Gospodarz")
        team_b = st.text_input("Gosc")
        add = st.form_submit_button("Dodaj mecz")
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
            st.write("Wpisz wynik meczu (uruchomi przeliczanie punktow)")
            labels = {
                f"#{m['id']} {m['team_a']} vs {m['team_b']}": m["id"] for m in scheduled
            }
            choice = st.selectbox("Mecz", list(labels.keys()))
            c1, c2 = st.columns(2)
            ra = c1.number_input("Wynik gospodarzy", min_value=0, step=1, value=0)
            rb = c2.number_input("Wynik gosci", min_value=0, step=1, value=0)
            save = st.form_submit_button("Zapisz wynik")
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


def main():
    handle_login_callback()

    if "access_token" not in st.session_state:
        render_login()
        return

    token = st.session_state["access_token"]
    roles = st.session_state.get("roles", [])

    st.sidebar.write(f"Zalogowano: **{st.session_state.get('username')}**")
    st.sidebar.write(f"Role: {', '.join(roles) or 'brak'}")
    if st.sidebar.button("Wyloguj"):
        st.session_state.clear()
        st.rerun()

    # Podglad diagnostyczny zawartosci tokenu (do debugowania rol).
    with st.sidebar.expander("Debug: zawartosc tokenu (JWT)"):
        st.json(st.session_state.get("claims", {}))
        st.caption("Surowy access_token (do skopiowania):")
        st.code(token, language="text")

    st.title("TyperCloud")
    try:
        matches = render_matches(token)
        render_prediction_form(token, matches)
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
