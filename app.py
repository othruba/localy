"""Interface Streamlit do Localy."""

import logging

import streamlit as st

from src.config import ROOT, load_catalog, load_destinations, read_yaml
from src.data import load_data
from src.llm import interpret_query
from src.map import make_map, select_scores
from src.scoring import score_cells


logger = logging.getLogger(__name__)


STYLE = """
<style>
.stApp {background: #f5f8f7; color: #18302e;}
.block-container {max-width: 1500px; padding-top: 2rem;}
[data-testid="stSidebar"] {background: #edf4f1;}
[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px;
}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
    border-radius: 12px; background: #147d72; border-color: #147d72;
    min-height: 44px; font-weight: 650;
}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primary"]:hover {
    background: #0d665d; border-color: #0d665d;
}
.localy-eyebrow {letter-spacing: .12em; text-transform: uppercase;
    color: #147d72; font-size: .78rem; font-weight: 750; margin-bottom: .45rem;}
.localy-lead {color: #526b67; max-width: 760px; font-size: 1.08rem;}
</style>
"""


def list_cities():
    """Descobre cidades pelos YAMLs, sem fixar nomes no código."""
    cities = {}
    for path in sorted((ROOT / "config" / "cities").glob("*.yaml")):
        city = read_yaml(path)
        if not isinstance(city, dict) or city.get("id") != path.stem:
            raise ValueError(f"Configuração inválida: {path}")
        cities[city["id"]] = city
    return cities


def data_version(city_id):
    """Muda a chave do cache quando um Parquet da cidade é substituído."""
    folder = ROOT / "data" / "processed" / city_id
    files = ("grid.parquet", "poi_access.parquet", "destination_access.parquet")
    versions = []
    for name in files:
        path = folder / name
        versions.append((path.stat().st_mtime_ns, path.stat().st_size) if path.is_file() else None)
    return tuple(versions)


@st.cache_data(show_spinner=False)
def get_data(city_id, version):
    """Mantém os Parquets em cache entre análises e interações com o mapa."""
    return load_data(city_id)


def show_sidebar(criteria, destinations, catalog):
    """Exibe a interpretação sem permitir editar critérios nesta versão."""
    names = {item["id"]: item["name"] for item in destinations}
    with st.sidebar:
        st.header("Interpretação")
        if criteria.destinations:
            st.subheader("Destinos principais")
            for choice in criteria.destinations:
                st.write(f"{names[choice.destination_id]} — importância {choice.weight}/5")
        if criteria.poi_preferences:
            st.subheader("Serviços próximos")
            for choice in criteria.poi_preferences:
                label = catalog[choice.poi_type]["label"]
                st.write(f"{label} — importância {choice.weight}/5")
        st.subheader("Mobilidade")
        st.write("Serviços: caminhada até o mais próximo, em até 30 minutos.")
        st.write("Destinos: menor tempo entre caminhada e transporte público, em até 60 minutos.")
        st.caption("Sem trajeto no limite calculado = zero ponto naquele critério.")


def main():
    st.set_page_config(page_title="Localy", page_icon="🗺️", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown('<div class="localy-eyebrow">Localy · descubra sua região</div>', unsafe_allow_html=True)
    st.title("Encontre um lugar que combina com sua rotina")
    st.markdown(
        '<p class="localy-lead">Conte seus destinos, interesses e o que gosta de ter por perto. '
        'Compare as regiões com melhor acesso em um mapa mais leve e fácil de explorar.</p>',
        unsafe_allow_html=True,
    )

    try:
        cities = list_cities()
        if not cities:
            st.error("Nenhuma cidade configurada em config/cities.")
            return
    except ValueError as error:
        st.error(str(error))
        return

    with st.container(border=True):
        with st.form("query_form"):
            city_id = st.selectbox(
                "Cidade",
                options=list(cities),
                index=list(cities).index("ponta_grossa") if "ponta_grossa" in cities else 0,
                format_func=lambda value: cities[value]["name"],
            )
            query = st.text_area(
                "O que importa na sua rotina?",
                placeholder="Ex.: Vou estudar na UFPR e quero acesso a arte, cultura e cafés.",
                height=100,
            )
            submitted = st.form_submit_button("Explorar regiões", type="primary")

    if submitted:
        # Descarta a análise anterior mesmo quando a nova pergunta falha.
        st.session_state.pop("analysis", None)
        version = data_version(city_id)
        if not query.strip():
            st.warning("Descreva o que você procura antes de analisar.")
        elif None in version:
            st.warning(
                f"{cities[city_id]['name']} ainda não tem todos os pré-cálculos. "
                f"Execute: uv run python -m scripts.precompute_accessibility --city {city_id}"
            )
        else:
            try:
                with st.spinner("Interpretando a consulta e pontuando as regiões..."):
                    grid, pois, destinations_access = get_data(city_id, version)
                    criteria = interpret_query(query, city_id)
                    scores = score_cells(criteria, grid, pois, destinations_access)
                # Uma nova chave limpa qualquer seleção antiga do mapa.
                st.session_state["analysis_serial"] = st.session_state.get("analysis_serial", 0) + 1
                st.session_state["analysis"] = {
                    "serial": st.session_state["analysis_serial"],
                    "city_id": city_id,
                    "criteria": criteria,
                    "scores": scores,
                }
            except (ValueError, RuntimeError) as error:
                st.error(f"Não foi possível analisar: {error}")
            except Exception:
                logger.exception("Erro inesperado na análise")
                st.error("Não foi possível analisar. Confira a conexão e a chave Gemini no .env.")

    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info("Escolha uma cidade e descreva seus interesses para descobrir as melhores regiões.")
        return

    city_id = analysis["city_id"]
    criteria = analysis["criteria"]
    scores = analysis["scores"]
    destinations = load_destinations(city_id)
    catalog = load_catalog()
    show_sidebar(criteria, destinations, catalog)

    st.subheader(f"Regiões em {cities[city_id]['name']}")
    share = st.slider("Mostrar as melhores regiões", min_value=5, max_value=25, value=10, step=5,
                      format="%d%%")
    visible = select_scores(scores, share)
    left, middle, right = st.columns(3)
    left.metric("Melhor pontuação", f"{scores.score.max():.1f}/100")
    middle.metric("Regiões em destaque", f"{len(visible):,}")
    right.metric("Regiões avaliadas", f"{len(scores):,}")
    st.caption(
        "Apenas as regiões mais bem avaliadas aparecem em verde translúcido, sem bordas. "
        "Passe o cursor para ver locais e tempos; selecione uma célula para detalhes."
    )
    deck = make_map(scores, criteria, cities[city_id], destinations, catalog, percent=share)
    event = st.pydeck_chart(
        deck,
        height=650,
        width="stretch",
        on_select="rerun",
        selection_mode="single-object",
        key=f"localy_map_{analysis['serial']}_{share}",
        alt="Mapa de hexágonos coloridos pela pontuação de acessibilidade.",
    )
    chosen = event.selection.objects.get("hexagons", [])
    if chosen:
        cell = chosen[0]
        with st.container(border=True):
            st.subheader(f"Região selecionada · {cell['score']:.1f}/100")
            for detail in cell["details"]:
                st.write(detail)

    st.caption(
        f"{len(scores):,} células avaliadas. Cenário de transporte: "
        f"{cities[city_id]['reference_datetime']} ({cities[city_id]['timezone']}). "
        "Os horários são os do GTFS instalado, não dados em tempo real."
    )


if __name__ == "__main__":
    main()
