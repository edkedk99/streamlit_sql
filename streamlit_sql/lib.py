from streamlit import session_state as ss


def init_ss(key: str, value=None):
    if key not in ss:
        ss[key] = value
