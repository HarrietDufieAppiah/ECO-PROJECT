"""
Food Waste Treatment — Pareto Explorer
========================================
A Streamlit dashboard over the Pareto-optimal results your GAMSPy/BARON
notebook (DetermineSceanrio1.ipynb) produces: for each feedstock scenario,
the cost (NAC) vs. GHG emissions vs. marine eutrophication tradeoff across
technology blends (shredding/mechanical -> biological pretreatment -> HTL /
anaerobic digestion / landfill / composting / wastewater treatment /
incineration -> gas upgrading).

IMPORTANT — architecture: this app does NOT run any optimization solver.
It only reads pre-solved CSV files from data/. The heavy BARON solve should
be run once, offline, wherever you have BARON access (see the README) — not
inside this app. That is what makes this deployable for free on Streamlit
Community Cloud: no solver license, no long-running compute, just plotting
already-computed results.

To use your real results instead of the bundled placeholder data: replace
the three files in data/ with your notebook's actual output, keeping the
exact same filenames and columns:
  - data/pareto_all_scenarios.csv   (notebook Cell 99 output)
  - data/scenario_comparison.csv    (notebook Cell 85 output)
  - data/feedstock_composition.csv  (the 5 feed dicts in notebook Cell 83,
                                      one row per scenario)
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit as st
import streamlit.components.v1 as components


DATA_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------------------
# Palette (validated categorical order — see the dataviz color formula:
# fixed order, never cycled, colors follow the entity not its rank)
# ---------------------------------------------------------------------------
CAT = {
    "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a",
    "yellow": "#eda100", "magenta": "#e87ba4", "green": "#008300",
}
TECH_COLOR = {  # fixed assignment, one color per conversion route, in order
    "HTL": CAT["blue"], "AND": CAT["orange"], "SLF": CAT["aqua"],
    "CMP": CAT["yellow"], "WWT": CAT["magenta"], "INC": CAT["green"],
}
SEQ_BLUE = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # light->dark
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"

TECH_NAMES = {
    "HTL": "Hydrothermal liquefaction", "AND": "Anaerobic digestion",
    "SLF": "Landfill", "CMP": "Composting", "WWT": "Wastewater treatment",
    "INC": "Incineration",
}

st.set_page_config(page_title="Food Waste Treatment Explorer", layout="wide")


# ---------------------------------------------------------------------------
# Landing page (hero) — the app's front door. A plain HTML/CSS section
# (no external image, so it has zero network dependency) with a headline,
# a short explainer, the 5 feedstock scenarios as chips, and a CTA that
# navigates into the dashboard via a query param. Streamlit re-runs this
# whole script on every navigation, so the routing check below is enough —
# no session-state page-machine needed.
# ---------------------------------------------------------------------------
# Fallback hero photo: free-to-use (Pexels license, no attribution required),
# loaded straight from Pexels' CDN by the VIEWER's browser -- not fetched by
# this server, so it works regardless of this machine's own network access.
# To use your own photo instead: drop a file named hero.jpg (or hero.png) in
# an `assets/` folder next to app.py -- it's picked up automatically and
# takes priority over this URL, no code changes needed.
FALLBACK_HERO_IMAGE_URL = (
    "https://images.pexels.com/photos/7262910/pexels-photo-7262910.jpeg"
    "?auto=compress&cs=tinysrgb&w=1920"
)


def _hero_background_css():
    """Local assets/hero.* wins if present (embedded as a data URI so it
    works fully offline); otherwise falls back to the URL above."""
    assets_dir = Path(__file__).parent / "assets"
    for ext, mime in [("jpg", "jpeg"), ("jpeg", "jpeg"), ("png", "png"), ("webp", "webp")]:
        candidate = assets_dir / f"hero.{ext}"
        if candidate.exists():
            import base64
            encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
            return f"url('data:image/{mime};base64,{encoded}')"
    return f"url('{FALLBACK_HERO_IMAGE_URL}')"


HERO_HTML_TEMPLATE = """
<style>
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
  header[data-testid="stHeader"] { display: none; }
  div[data-testid="stDecoration"] { display: none; }
  div[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
  /* Streamlit has renamed these internal classes across versions --
     cover both the old names and the current (2024+) data-testid ones
     so this keeps working regardless of which Streamlit version runs it. */
  div[data-testid="stAppViewContainer"] > .main,
  div[data-testid="stMain"] {
      padding-top: 0 !important;
  }
  div[data-testid="stAppViewContainer"] > .main .block-container,
  div[data-testid="stMainBlockContainer"],
  .block-container {
      padding: 0 !important; max-width: 100% !important;
  }
  .hero {
      position: relative;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 4vh 8vw;
      color: #ffffff;
      overflow: hidden;
  }
  .hero-bg {
      position: absolute;
      inset: 0;
      background: __HERO_BG__ center / cover no-repeat;
      animation: hero-zoom 20s ease-in-out infinite alternate;
      z-index: 0;
  }
  .hero-overlay {
      position: absolute;
      inset: 0;
      background: linear-gradient(100deg, rgba(8,10,9,0.92) 0%, rgba(8,10,9,0.72) 38%, rgba(8,10,9,0.30) 62%, rgba(8,10,9,0.55) 100%);
      z-index: 1;
  }
  .hero h1, .hero-card, .hero-cta {
      position: relative;
      z-index: 2;
  }
  @keyframes hero-zoom {
      from { transform: scale(1); }
      to   { transform: scale(1.12); }
  }
  @media (prefers-reduced-motion: reduce) {
      .hero-bg { animation: none; }
  }
  .hero h1 {
      font-size: clamp(1.9rem, 3.6vw, 3.1rem);
      font-weight: 800; line-height: 1.2; margin: 0 0 0.3em 0;
      max-width: 34ch;
  }
  .hero h1 .accent { color: #1baf7a; }
  .hero-card {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      backdrop-filter: blur(6px);
      border-radius: 12px;
      padding: 1.1em 1.3em;
      max-width: 46ch;
      margin: 1.2em 0 1.6em 0;
      font-size: 1.02rem;
      color: #e7e6e1;
  }
  .hero-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 1.6em; }
  .hero-chip {
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.16);
      color: #c3c2b7; font-size: 0.85rem;
      padding: 0.35em 0.9em; border-radius: 999px;
  }
  .hero-cta {
      display: inline-flex; align-items: center; gap: 0.5em;
      background: #1baf7a; color: #0b0b0b !important;
      font-weight: 700; text-decoration: none !important;
      padding: 0.85em 1.6em; border-radius: 999px; width: fit-content;
      font-size: 1.05rem; transition: transform 0.15s ease, background 0.15s ease;
  }
  .hero-cta:hover { background: #199e70; transform: translateY(-1px); }
  .hero-link {
      display: block; margin-top: 0.9em; font-family: monospace;
      font-size: 0.85rem; color: #c3c2b7; text-decoration: underline;
  }
</style>

<div class="hero">
  <div class="hero-bg"></div>
  <div class="hero-overlay"></div>
  <h1>Turn a waste stream into a product.<br/>
      <span class="accent">Find the cheapest, cleanest route to get there.</span></h1>

  <div class="hero-card">
      Enter what you're throwing away. This app runs every viable
      processing pathway and returns the one that costs least, pollutes
      least, or balances both.
      <a class="hero-link" href="?page=app">see how the model works</a>
  </div>

  <a class="hero-cta" href="?page=app">Describe your waste stream →</a>
</div>
"""


def render_landing():
    hero_bg = _hero_background_css()
    st.markdown(
        HERO_HTML_TEMPLATE.replace("__HERO_BG__", hero_bg),
        unsafe_allow_html=True,
    )


if st.query_params.get("page") != "app":
    render_landing()
    st.stop()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    pareto_path = DATA_DIR / "pareto_all_scenarios.csv"
    comparison_path = DATA_DIR / "scenario_comparison.csv"
    feedstock_path = DATA_DIR / "feedstock_composition.csv"
    cost_path = DATA_DIR / "cost_breakdown.csv"

    if not pareto_path.exists():
        st.error(
            f"Missing {pareto_path.name} in data/. Run "
            "`python generate_sample_data.py` for placeholder data, or drop "
            "in your real notebook output under that filename."
        )
        st.stop()

    pareto = pd.read_csv(pareto_path, encoding="utf-8")
    comparison = pd.read_csv(comparison_path, encoding="utf-8") if comparison_path.exists() else None
    feedstock = pd.read_csv(feedstock_path, encoding="utf-8") if feedstock_path.exists() else None
    cost = pd.read_csv(cost_path, encoding="utf-8") if cost_path.exists() else None

    # Drop rows that didn't converge (Quality == "Failed" / NaN objective),
    # same rule the notebook's own Cell 99 applies before plotting.
    if "Quality" in pareto.columns:
        pareto = pareto[pareto["Quality"] != "Failed"]
    pareto = pareto.dropna(subset=["NAC_MUSD_per_yr", "GHG_tCO2e_per_yr", "EP_marine_tpy"])
    return pareto, comparison, feedstock, cost


pareto_df, comparison_df, feedstock_df, cost_df = load_data()
is_placeholder = True  # flip to False once you're on real solved data
scenarios = sorted(pareto_df["Scenario"].unique())

# ---------------------------------------------------------------------------
# Sidebar — vertical section navigation (replaces the old scenario-picker
# sidebar). "Feed Inputs" now owns the scenario choice; every other section
# reads it back from st.session_state so the choice carries across tabs.
# ---------------------------------------------------------------------------
st.sidebar.markdown("[← Back to home](?)")
st.sidebar.title("Food Waste Treatment Explorer")

# Results has 3 sub-pages, listed right under it in the sidebar (indented
# with an arrow). Placeholders for now: what each one shows is decided later.
RESULTS_SUBVIEWS = [
    "Lowest Cost Pathways",
    "Lowest Environmental Impact Pathways",
    "Best Cost & Environmental Impact Pathways",
]

if "pending_nav_choice" in st.session_state:
    st.session_state["nav_choice"] = st.session_state.pop("pending_nav_choice")

# The 3 Results sub-pages stay hidden until Results itself (or one of them)
# is the active selection, then they appear indented right under it (no
# arrow, just leading spaces so it still reads as nested).
SUB_INDENT = "    "
_current_choice = st.session_state.get("nav_choice", "Instructions")
_results_active = _current_choice == "Results" or _current_choice.startswith(SUB_INDENT)

NAV_OPTIONS = [
    "Instructions",
    "Feed Inputs",
    "Technology Specifications",
    "Cost Specifications",
    "Results",
    *([f"{SUB_INDENT}{sub}" for sub in RESULTS_SUBVIEWS] if _results_active else []),
    "Environmental Justice",
]

choice = st.sidebar.radio(
    "Section", NAV_OPTIONS, key="nav_choice", label_visibility="collapsed"
)

if choice.startswith(SUB_INDENT):
    section = "Results"
    results_subview = choice[len(SUB_INDENT):]
else:
    section = choice
    results_subview = None

if "selected_scenario" not in st.session_state:
    st.session_state["selected_scenario"] = None  # gate: nothing chosen yet in Feed Inputs


# ---------------------------------------------------------------------------
# Section: Instructions
# ---------------------------------------------------------------------------
def render_instructions():
    st.title("Instructions")
    st.write(
        "This tool helps you figure out the best way to treat a food-waste "
        "stream: the option that costs the least, pollutes the least, or "
        "strikes a balance between the two. Behind the scenes, it runs an "
        "optimization model that tests every combination of treatment technologies "
        "in the prcoessing pipeline and works out exactly how much of your waste"
        "stream should go through each one to hit your goal on any of "
        "these objectives."
    )

    st.subheader("The processing pipeline")
    pipeline_diagram = Path(__file__).parent / "assets" / "pipeline_diagram.png"
    if pipeline_diagram.exists():
        import base64
        encoded = base64.b64encode(pipeline_diagram.read_bytes()).decode("ascii")
        st.markdown(
            f"""
            <div style="text-align:center;">
              <img src="data:image/png;base64,{encoded}"
                   style="max-height:48vh;max-width:100%;object-fit:contain;" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info(
            "Add the flowsheet diagram at assets/pipeline_diagram.png to "
            "show it here."
        )
    legend = [
        ("#3f9142", "Pretreatment", [
            "<strong>Mechanical:</strong> Shredding (SHR), Maceration (MCR)",
            "<strong>Biological:</strong> Aerobic biodigestion (AER), "
            "Enzymatic hydrolysis (ENZ)",
        ]),
        ("#7b2d8e", "Conversion", [
            "Hydrothermal liquefaction (HTL)",
            "Anaerobic digestion (AND)",
            "Composting (CMP)",
            "Sanitary landfill (SLF)",
            "Wastewater treatment (WWT)",
            "Incineration (INC)",
        ]),
        ("#8b4a2b", "Recovery &amp; Upgrading", [
            "Centrifugation (CEN), Filtration (FLT)",
            "Amine scrubbing (ABS), PSA gas upgrading (PSA)",
            "Steam turbine (STB)",
        ]),
    ]
    lcols = st.columns(3)
    for col, (color, group_title, items) in zip(lcols, legend):
        items_html = "".join(f"<li>{item}</li>" for item in items)
        with col:
            st.markdown(
                f"""
                <div style="font-weight:700;color:{color};margin-bottom:0.4em;">
                    {group_title}</div>
                <ul style="margin:0;padding-left:1.1em;color:{INK_SECONDARY};
                           font-size:0.92rem;line-height:1.6;">
                    {items_html}
                </ul>
                                """,
                unsafe_allow_html=True,
            )

    st.subheader("What the model balances")

    objectives = [
        (CAT["blue"], "Cost", "Net Annualized Cost (NAC): capital and "
                           "operating expense, minus revenue from "
                           "recovered products, in M$/yr."),
        (CAT["orange"], "GHG emissions", "The route's greenhouse-gas "
                                          "footprint, in tCO2e/yr."),
        (CAT["aqua"], "Marine eutrophication", "Potential for excess "
                                            "nitrogen loading (to air, water, "
                                            "and soil) to reach coastal waters "
                                            "and drive algal overgrowth and "
                                            "oxygen depletion, in tN-eq/yr.")
    ]

    card_divs = []
    for color, obj_title, desc in objectives:
        card_divs.append(
            f'<div style="flex:1;display:flex;flex-direction:column;'
            f'background:{SURFACE};border:1px solid {GRIDLINE};'
            f'border-top:4px solid {color};border-radius:12px;padding:1.2em;'
            f'box-sizing:border-box;">'
            f'<div style="font-weight:700;margin-bottom:0.4em;color:{INK_PRIMARY};">'
            f'{obj_title}</div>'
            f'<div style="color:{INK_SECONDARY};font-size:0.92rem;">{desc}</div>'
            f'</div>'
        )

    cards_html = (
        '<div style="display:flex;align-items:stretch;gap:1rem;'
        'font-family:\'Source Sans Pro\',-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif;">'
        + "".join(card_divs)
        + "</div>"
    )
    components.html(cards_html, height=220, scrolling=False)



# ---------------------------------------------------------------------------
# Section: Feed Inputs
# ---------------------------------------------------------------------------
# Wet-basis composition categories, in the same order populate_feed() in the
# notebook builds them (CBH/PRT/FAT/ASH/FC scaled by (1 - moisture), OTH =
# volatile matter left over, WATER = moisture). Water gets a neutral/muted
# color since it's diluent, not an organic component; the other six get the
# fixed categorical palette, one color per entity, never reused elsewhere.
FEED_COMPONENTS = [
    ("WATER", "Water", "#c9c3b4"),
    ("PRT", "Protein", CAT["blue"]),
    ("CBH", "Carbohydrates", CAT["orange"]),
    ("FAT", "Fat / Lipid", CAT["aqua"]),
    ("ASH", "Ash", CAT["yellow"]),
    ("OTH", "Other Organics", CAT["magenta"]),
    ("FC", "Fixed Carbon", CAT["green"]),
]


def _wet_basis_composition(feed_row):
    """Same math as populate_feed() in the notebook: CBH/PRT/FAT/ASH/FC are
    dry-basis %, OTH is the leftover volatile matter, all scaled down by
    (1 - moisture) so they close to 1.0 together with WATER."""
    dry = {
        "CBH": feed_row["Carbohydrate (%)"],
        "PRT": feed_row["Protein (%)"],
        "FAT": feed_row["Lipid (%)"],
        "ASH": feed_row["Ash (%)"],
        "FC": feed_row["Fixed carbon (%)"],
    }
    dry["OTH"] = feed_row["Volatile matter (%)"] - dry["CBH"] - dry["PRT"] - dry["FAT"]
    x_mc = feed_row["Moisture (%)"] / 100.0
    sol = {c: v / 100.0 * (1.0 - x_mc) for c, v in dry.items()}
    scale = (1.0 - x_mc) / sum(sol.values())
    sol = {c: v * scale for c, v in sol.items()}
    sol["WATER"] = x_mc
    return sol


def _feed_energy_stats(feed_row):
    """Every value here is either a direct pass-through of a field in the
    notebook's feed dict (HHV, Moisture, Volatile matter, all commented
    there with their exact basis) or the notebook's own formula (C:N, the
    molar ratio printed by populate_feed()). No derived "VS"/"TS" here --
    the notebook has no such field for the raw feed (TS_AND/TS_MCR in the
    notebook are digester/macerator OPERATING targets, not a feed
    property), so showing one would not be traceable to the code."""
    cn_molar = (feed_row["C (%)"] / 12.011) / (feed_row["N (%)"] / 14.01)
    return {
        "hhv": feed_row["HHV (MJ/kg)"],           # dry basis, per notebook comment
        "moisture_pct": feed_row["Moisture (%)"],  # % of wet mass, per notebook comment
        "vm_pct": feed_row["Volatile matter (%)"],  # % of dry mass, per notebook comment
        "cn": cn_molar,
    }


def render_feed_inputs(scenarios, feedstock_df):
    st.title("Feed Inputs")
    st.write(
        "Select the food waste type you are working with, then review the "
        "stream details below. Everything here is propagated through the "
        "model and carries through to the Results."
    )
    st.subheader("Food Waste Type")
    current = st.session_state.get("selected_scenario")
    index = scenarios.index(current) if current in scenarios else None
    choice = st.selectbox(
        "Food waste type",
        scenarios,
        index=index,
        placeholder="Select a food waste type...",
        label_visibility="collapsed",
    )
    if choice is None:
        st.info("Please select a food waste type to continue.")
        return
    st.session_state["selected_scenario"] = choice

    if feedstock_df is None or choice not in set(feedstock_df["Scenario"]):
        st.info("Feed composition data isn't available for this scenario yet.")
        return
    feed_row = feedstock_df[feedstock_df["Scenario"] == choice].iloc[0]
    stats = _feed_energy_stats(feed_row)

    # Everything below renders as one bordered card right under the
    # dropdown, so picking a type visibly "opens up" its details in one
    # place instead of them being scattered down the page.
    details = st.container(border=True)
    left, right = details.columns([1, 1], gap="large")

    with left:
        st.subheader("Feed Stream Conditions")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "Feed rate (kg/hr)", min_value=0.0, step=100.0, format="%.2f",
                value=float(st.session_state.get("feed_rate_kgph", 10000.0)),
                key="feed_rate_kgph",
            )
        with c2:
            st.number_input(
                "Operating hours (hr/yr)", min_value=0.0, max_value=8760.0,
                step=10.0, format="%.2f",
                value=float(st.session_state.get("operating_hours", 7920.0)),
                key="operating_hours",
            )

        st.subheader("Facility Location")
        st.text_input(
            "Facility zip code", placeholder="e.g. 08028",
            key="facility_zip", label_visibility="collapsed",
        )
        st.caption("Enter a zip code to enable the Environmental Justice assessment.")

        st.subheader("Composition (wet basis)")
        wet = _wet_basis_composition(feed_row)
        reset = st.button("↺ Reset to this feedstock's typical composition")
        edited = {}
        comp_cols = st.columns(2)
        for i, (code, label, _color) in enumerate(FEED_COMPONENTS):
            comp_key = f"feed_comp_{choice}_{code}"
            if reset and comp_key in st.session_state:
                del st.session_state[comp_key]
            with comp_cols[i % 2]:
                edited[code] = st.number_input(
                    label, min_value=0.0, max_value=1.0, step=0.001, format="%.4f",
                    value=round(float(st.session_state.get(comp_key, wet[code])), 4),
                    key=comp_key,
                )
        total = sum(edited.values())
        if abs(total - 1.0) < 0.005:
            st.caption(f"Total mass fraction: **{total:.4f}** (closes to 1.0)")
        else:
            st.warning(
                f"Total mass fraction: **{total:.4f}**. It should sum to "
                "1.0; adjust the values above."
            )

    with right:
        st.subheader("Energy & Organic Content")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("HHV, dry (MJ/kg)", f"{stats['hhv']:.2f}")
        s2.metric("Moisture (%)", f"{stats['moisture_pct']:.2f}")
        s3.metric("VM, dry (%)", f"{stats['vm_pct']:.2f}")
        s4.metric("C:N ratio (molar)", f"{stats['cn']:.1f}")

        st.subheader("Composition Breakdown")
        names = [label for _, label, _ in FEED_COMPONENTS]
        values = [edited[code] * 100 for code, _, _ in FEED_COMPONENTS]
        colors = [color for _, _, color in FEED_COMPONENTS]
        # legend spells out the percentage per component, e.g.
        # "Water: 75.95%", not just a color key you have to hover to read.
        labels = [f"{name}: {value:.2f}%" for name, value in zip(names, values)]
        fig = go.Figure(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                sort=False,
                marker=dict(colors=colors, line=dict(color=SURFACE, width=2)),
                textinfo="none",
                hovertemplate="%{label}<extra></extra>",
            )
        )
        fig.update_layout(
            showlegend=True,
            legend=dict(font=dict(color=INK_PRIMARY)),
            paper_bgcolor=SURFACE,
            margin=dict(t=10, b=10, l=10, r=10),
            height=340,
            annotations=[dict(
                text=choice, x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color=INK_PRIMARY),
            )],
        )
        st.plotly_chart(fig, width="stretch")

    details.caption(
        "Feed rate and operating hours scale the cost and emissions "
        "totals; composition drives the mass balance through each "
        "technology."
    )


# ---------------------------------------------------------------------------
# Section: Technology Specifications
# ---------------------------------------------------------------------------
# Every value below is a scalar straight out of the notebook's own scalar
# declarations (Cell "Scalors" / sc(...) calls), not estimated. No stream
# numbers here (that's flowsheet-internal plumbing, not a spec); the
# "about" line just says what goes in and what comes out in plain terms.
# The parameter list is curated, not a dump of every scalar the notebook
# defines for each technology -- vessel-sizing details (working volume
# fraction), and parameters that are mostly redundant with one already
# shown (e.g. SLF's DOC-dissimilated and cover-oxidation terms feed the
# same capture story as "Gas capture"), are left out so what's shown is
# what actually distinguishes the technology.
TECH_DETAILS = {
    "HTL": {
        "params": [
            ("Reactor temperature", "340", "degC"),
            ("Residence time", "1.0", "h"),
            ("Dilution water ratio", "7.0", "kg water / kg dry solids"),
            ("Heat recovery efficiency", "70", "%"),
            ("HTL gas heating value", "4.2", "MJ/kg"),
        ],
    },
    "AND": {
        "params": [
            ("Residence time", "30", "days"),
            ("Temperature", "35 (mesophilic)", "degC"),
            ("Design solids content", "10", "% TS, wet"),
            ("VS destruction", "80", "%"),
            ("Biogas capture", "97", "%"),
        ],
    },
    "SLF": {
        "params": [
            ("Degradable organic carbon", "35.8", "% of waste"),
            ("Gas capture", "65", "%"),
            ("Landfill depth", "10", "m"),
        ],
    },
    "CMP": {
        "params": [
            ("Residence time", "5", "days"),
            ("VS degraded", "50", "%"),
            ("Excess air ratio", "2.5", "x stoichiometric"),
        ],
    },
    "WWT": {
        "params": [
            ("Solids retention time", "1.0", "days"),
            ("F/M loading", "4.0", "kg BOD / kg MLSS / day"),
            ("MLSS", "5.0", "g/L"),
        ],
    },
    "INC": {
        "params": [
            ("Excess air ratio", "1.2", "x stoichiometric"),
            ("Self-sustaining threshold", "3.5", "MJ/kg wet feed (LHV)"),
            ("Auxiliary fuel", "Natural gas", "48 MJ/kg, used below the "
                                               "threshold"),
        ],
    },
}


def render_technology_specifications():
    st.title("Technology Specifications")
    st.write(
        "These are the treatment technologies the model is allowed to "
        "choose from. Each one can take a fractional share of the waste "
        "stream."
    )

    tech_summaries = [
        ("HTL", "Heats wet waste under pressure without drying it, "
                "converting it into biocrude."),
        ("AND", "Microbes break waste down without oxygen in a sealed "
                "digester, producing biogas."),
        ("SLF", "Buries waste in an engineered landfill, where it "
                "decomposes and releases gas for capture."),
        ("CMP", "Breaks waste down aerobically over time, turning it "
                "into a stable soil product."),
        ("WWT", "Treats wet, dilute waste with activated sludge, "
                "converting organics into biosolids and treated effluent."),
        ("INC", "Combusts the waste at high temperature, recovering "
                "its energy as heat and power."),
    ]
    tcols = st.columns(3)
    for i, (code, desc) in enumerate(tech_summaries):
        with tcols[i % 3]:
            st.markdown(
                f"""
                <div style="border-left:4px solid {TECH_COLOR[code]};
                            background:{SURFACE};border-radius:6px;
                            padding:0.8em 1em;margin-bottom:0.8em;">
                  <div style="font-weight:700;color:{INK_PRIMARY};">
                      {TECH_NAMES[code]}</div>
                  <div style="color:{INK_SECONDARY};font-size:0.88rem;">
                      {desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.subheader("Process Parameters")
    tech_choice = st.selectbox(
        "Choose a technology",
        list(TECH_DETAILS.keys()),
        format_func=lambda code: TECH_NAMES.get(code, code),
    )
    detail = TECH_DETAILS[tech_choice]
    with st.container(border=True):
        st.markdown(
            f"""<div style="border-left:4px solid {TECH_COLOR[tech_choice]};
                            padding-left:0.8em;font-size:1.15rem;
                            font-weight:700;color:{INK_PRIMARY};">
                    {TECH_NAMES[tech_choice]} ({tech_choice})</div>""",
            unsafe_allow_html=True,
        )
        params_df = pd.DataFrame(
            detail["params"], columns=["Parameter", "Value", "Unit / note"]
        )
        st.table(params_df.set_index("Parameter"))
    st.caption(
        "Pretreatment (shredding, maceration, aerobic, enzymatic) and "
        "Recovery & Upgrading (centrifuge, filter, amine scrubbing, PSA, "
        "steam turbine) technologies aren't broken out here yet."
    )


# ---------------------------------------------------------------------------
# Section: Cost Specifications
# ---------------------------------------------------------------------------
# All 15 technologies in the superstructure (mechanical + biological
# pretreatment, conversion, recovery & upgrading) — every C0/Q0/Wsp/Nlbr
# the notebook's costing cell actually sums over (Cell 6 / Cell 62).
TECH_COST_PARAMS = {
    "SHR": {"c0": 111_000, "q0": 10_000, "q0_unit": "kg/h throughput", "wsp": 0.02, "nlbr": 0.1,
            "stage": "Mechanical pretreatment"},
    "MCR": {"c0": 111_000, "q0": 60_000, "q0_unit": "kg/h throughput", "wsp": 0.10, "nlbr": 0.1,
            "stage": "Mechanical pretreatment"},
    "AER": {"c0": 882_000, "q0": 15_000, "q0_unit": "m3 vessel volume", "wsp": 0.04, "nlbr": 0.5,
            "stage": "Biological pretreatment"},
    "ENZ": {"c0": 882_000, "q0": 15_000, "q0_unit": "m3 vessel volume", "wsp": 0.04, "nlbr": 0.5,
            "stage": "Biological pretreatment"},
    "HTL": {"c0": 645_000, "q0": 40, "q0_unit": "m3 reactor volume", "wsp": 2.0, "nlbr": 2.0,
            "stage": "Conversion"},
    "AND": {"c0": 594_000, "q0": 1_000, "q0_unit": "m3 digester volume", "wsp": 0.005, "nlbr": 0.02,
            "stage": "Conversion"},
    "SLF": {"c0": 450_000, "q0": 0.15, "q0_unit": "acres of new land/yr", "wsp": 0.5, "nlbr": 1.0,
            "stage": "Conversion"},
    "CMP": {"c0": 786_000, "q0": 350, "q0_unit": "m3 vessel volume", "wsp": 0.02, "nlbr": 0.5,
            "stage": "Conversion"},
    "WWT": {"c0": 8_000_000, "q0": 15_000, "q0_unit": "m3 aeration tank volume", "wsp": 0.04, "nlbr": 0.5,
            "stage": "Conversion"},
    "INC": {"c0": 4_700_000, "q0": 8_000, "q0_unit": "kg/h throughput", "wsp": 0.05, "nlbr": 1.0,
            "stage": "Conversion"},
    "CEN": {"c0": 66_000, "q0": 0.01, "q0_unit": "m2, sigma factor", "wsp": 0.1, "nlbr": 1.0,
            "stage": "Recovery & upgrading"},
    "FLT": {"c0": 39_000, "q0": 80, "q0_unit": "m2 membrane area", "wsp": 0.1, "nlbr": 0.5,
            "stage": "Recovery & upgrading"},
    "ABS": {"c0": 30_000, "q0": 32, "q0_unit": "Nm3/h biogas", "wsp": 0.1, "nlbr": 0.01,
            "stage": "Recovery & upgrading"},
    "PSA": {"c0": 80_000, "q0": 50, "q0_unit": "Nm3/h biogas", "wsp": 0.4, "nlbr": 0.01,
            "stage": "Recovery & upgrading"},
    "STB": {"c0": 45_000, "q0": 30_000, "q0_unit": "kW electric output", "wsp": 0.02, "nlbr": 0.05,
            "stage": "Recovery & upgrading"},
}

ALL_TECH_NAMES = {
    "SHR": "Shredder", "MCR": "Macerator",
    "AER": "Aerobic digester", "ENZ": "Enzymatic hydrolysis",
    **TECH_NAMES,
    "CEN": "Centrifuge", "FLT": "Membrane filtration",
    "ABS": "Amine absorption", "PSA": "Pressure swing adsorption",
    "STB": "Steam turbine",
}

# Conversion techs keep their identity color from TECH_COLOR (used elsewhere
# in the app); every other stage gets one shared neutral accent, since these
# are never shown as parallel series in a chart — just one card at a time.
ALL_TECH_COLOR = {code: TECH_COLOR.get(code, INK_MUTED) for code in TECH_COST_PARAMS}

# Each row: (label, key, default value, unit, note)
GLOBAL_COST_ASSUMPTIONS = [
    ("Six-tenths cost exponent", "nc", 0.67, "", "applied to capacity ratio, all technologies"),
    ("Bare-module cost multiplier", "bmc", 5.4, "x", "installed cost / purchase cost"),
    ("Capital recovery factor", "crf", 0.11, "/yr", "annualizes installed capital"),
    ("Working capital", "wc", 15.0, "% of FCI/yr", "annualized the same way as capital"),
    ("Insurance & property tax", "ins", 1.0, "% of FCI/yr", "FCI = fixed capital investment"),
    ("Facility overhead", "fac", 6.0, "% of FCI/yr", "maintenance, factory overhead, local taxes"),
    ("Operating hours", "tann", 7920.0, "h/yr", "= 330 days/yr, 24 h/day"),
    ("Labor rate", "clbr", 30.0, "$/h", "per operator"),
    ("Electricity", "celec", 0.10, "$/kWh", ""),
    ("Process steam", "cstm", 0.012, "$/kg", ""),
    ("Cooling water", "cpwt", 0.00005, "$/kg", ""),
    ("Process water", "cwater", 0.0053, "$/kg", "dilution water for MCR/HTL/AND/STB"),
    ("Natural gas", "cng", 0.25, "$/kg", "INC auxiliary firing, below the self-sustaining threshold"),
]

PRODUCT_PRICES = [
    ("Biomethane (CH4)", "ch4", 0.55, "$/kg", "AND biogas, upgraded"),
    ("Biocrude", "biocrude", 0.48, "$/kg", "HTL product"),
    ("Compost", "compost", 0.068, "$/kg", "CMP product"),
    ("Electricity", "elec_price", 0.10, "$/kWh", "from the INC waste-heat steam turbine"),
    ("Biosolids", "biosolids", 0.05, "$/kg", "WWT product"),
    ("Tipping fee received", "tip", 0.055, "$/kg feed", "revenue for accepting the waste at the gate"),
]

DISPOSAL_COSTS = [
    ("Shredder reject", "disp_reject", 0.055, "$/kg", ""),
    ("Aqueous phase (HTL/AND)", "disp_aq", 0.030, "$/kg", "high-strength organic wastewater, needs treatment"),
    ("Char / cake", "disp_char", 0.055, "$/kg", "HTL solids residue"),
    ("Landfill gate fee", "disp_land", 0.055, "$/kg", "charged on the feed entering SLF"),
    ("AD digestate", "disp_digestate", 0.005, "$/kg", "land-applied, not landfilled"),
]

COST_COMPONENTS = [
    ("Capital", CAT["blue"], "Capital_MUSD_per_yr",
     "Annualized capital. Equipment cost scales with capacity, a "
     "bare-module multiplier accounts for installation, and the capital "
     "recovery factor spreads it over the plant's life."),
    ("Facility overhead & insurance", CAT["orange"], "Overhead_MUSD_per_yr",
     "Maintenance, factory overhead, local taxes, and insurance, all sized "
     "as a share of installed capital."),
    ("Labor", CAT["aqua"], "Labor_MUSD_per_yr",
     "Operating labor, scaled from a reference staffing level by how the "
     "plant's throughput compares to that reference."),
    ("Utilities", CAT["yellow"], "Utilities_MUSD_per_yr",
     "Electricity, process steam, and cooling water consumed by whichever "
     "technologies the model selects."),
    ("Raw materials & disposal", CAT["magenta"], "Materials_MUSD_per_yr",
     "Process water, enzyme, amine makeup, auxiliary natural gas, and any "
     "landfill tipping fees."),
    ("Working capital", CAT["green"], "WorkingCapital_MUSD_per_yr",
     "A small running-capital reserve, annualized the same way as the "
     "main capital cost."),
]


def render_cost_specifications(cost_df, scenarios):
    st.title("Cost Specifications")
    st.write(
        "These are the cost, revenue, and disposal assumptions driving "
        "the model- equipment costs, labor rates, utility prices, product revenue, and disposal fee. "
        "Adjust any your of them below to test your own assumptions."
    )

    tab_tech, tab_global, tab_prices, tab_disposal = st.tabs(
        ["Technology capital & labor", "Global assumptions",
         "Product prices & fees", "Disposal costs"]
    )

    with tab_tech:
        tech_choice = st.selectbox(
            "Technology", list(TECH_COST_PARAMS.keys()),
            format_func=lambda c: f"{ALL_TECH_NAMES[c]} ({TECH_COST_PARAMS[c]['stage']})",
            key="cost_tech_select",
        )
        p = TECH_COST_PARAMS[tech_choice]
        st.markdown(
            f"""
            <div style="border-left:4px solid {ALL_TECH_COLOR[tech_choice]};
                        background:{SURFACE};border-radius:6px;
                        padding:0.9em 1.1em;margin:0.6em 0 1em 0;">
              <div style="font-weight:700;color:{INK_PRIMARY};">
                {ALL_TECH_NAMES[tech_choice]} ({tech_choice})
              </div>
              <div style="color:{INK_SECONDARY};font-size:0.85rem;">
                {p['stage']}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        tc1, tc2 = st.columns(2)
        tc1.number_input(
            "Reference purchase cost ($)", value=float(p["c0"]), step=1000.0,
            format="%.0f", key=f"cost_tech_c0_{tech_choice}",
            help="Equipment cost at the reference capacity, before installation.",
        )
        tc2.text_input(
            "Reference capacity", value=f"{p['q0']:g} {p['q0_unit']}",
            disabled=True, key=f"cost_tech_q0_{tech_choice}",
        )
        tc1.number_input(
            "Specific power (kW per unit capacity)", value=float(p["wsp"]),
            step=0.01, format="%.3f", key=f"cost_tech_wsp_{tech_choice}",
        )
        tc2.number_input(
            "Labor requirement (operators per unit capacity)", value=float(p["nlbr"]),
            step=0.01, format="%.3f", key=f"cost_tech_nlbr_{tech_choice}",
        )
        st.caption(
            "Purchase cost scales from the reference point by the six-tenths "
            "rule: cost = C0 × (capacity / reference capacity) ^ 0.67."
        )

    def _editable_params(rows):
        cols = st.columns(2)
        for i, (label, key, value, unit, note) in enumerate(rows):
            value = float(value)
            decimals = 0 if value >= 100 else (2 if value >= 1 else 5)
            with cols[i % 2]:
                st.number_input(
                    f"{label} ({unit})" if unit else label,
                    value=value, format=f"%.{decimals}f",
                    key=f"cost_param_{key}", help=note or None,
                )

    with tab_global:
        _editable_params(GLOBAL_COST_ASSUMPTIONS)

    with tab_prices:
        _editable_params(PRODUCT_PRICES)

    with tab_disposal:
        _editable_params(DISPOSAL_COSTS)


# ---------------------------------------------------------------------------
# Placeholder sections — wired up later
# ---------------------------------------------------------------------------
def render_placeholder(name):
    st.title(name)
    st.info(f"{name}: coming soon.")


def render_results_landing(subviews):
    st.title("Results")
    st.write("Choose a pathway to view its results.")
    for sub in subviews:
        if st.button(sub, key=f"results_landing_{sub}", width="stretch"):
            st.session_state["pending_nav_choice"] = f"{SUB_INDENT}{sub}"
            st.rerun()


# ---------------------------------------------------------------------------
# Section: Results (the dashboard)
# ---------------------------------------------------------------------------
def render_results(pareto_df, comparison_df, feedstock_df, cost_df, scenarios):
    selected_scenario = st.session_state.get("selected_scenario")
    if selected_scenario is None:
        st.title("Food Waste Treatment: Cost vs. Environmental Impact")
        st.info("Select a food waste type in Feed Inputs to see results.")
        return
    scenario_df = pareto_df[pareto_df["Scenario"] == selected_scenario].copy()

    st.title("Food Waste Treatment: Cost vs. Environmental Impact")
    st.caption(
        "Explore the Pareto-optimal tradeoff between annualized cost (NAC), "
        "greenhouse-gas emissions, and marine eutrophication potential "
        f"across food-waste treatment technology blends. Scenario: "
        f"**{selected_scenario}** (change it in Feed Inputs)."
    )

    # -----------------------------------------------------------------
    # KPI row for the selected scenario
    # -----------------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pareto points", len(scenario_df))
    k2.metric("Cheapest NAC (M$/yr)", f"{scenario_df['NAC_MUSD_per_yr'].min():.2f}")
    k3.metric("Lowest GHG (tCO2e/yr)", f"{scenario_df['GHG_tCO2e_per_yr'].min():,.0f}")
    k4.metric("Lowest marine EP (t N-eq/yr)", f"{scenario_df['EP_marine_tpy'].min():.2f}")

    tab_explorer, tab_blend, tab_cost, tab_compare, tab_feedstock, tab_data = st.tabs(
        ["Pareto explorer", "Technology blend", "Cost breakdown",
         "Compare scenarios", "Feedstock", "Data"]
    )

    # -------------------------------------------------------------
    # Tab 1 — Pareto explorer: NAC vs GHG, colored by EP (sequential = magnitude)
    # -------------------------------------------------------------
    with tab_explorer:
        st.subheader(f"{selected_scenario}: cost vs. GHG, colored by marine eutrophication")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=scenario_df["GHG_tCO2e_per_yr"],
                y=scenario_df["NAC_MUSD_per_yr"],
                mode="markers",
                marker=dict(
                    size=14,
                    color=scenario_df["EP_marine_tpy"],
                    colorscale=[[i / 4, c] for i, c in enumerate(SEQ_BLUE)],
                    colorbar=dict(title="Marine EP<br>(t N-eq/yr)"),
                    line=dict(width=1, color="white"),
                ),
                customdata=scenario_df[["Point", "Quality", "Config"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "NAC: %{y:.3f} M$/yr<br>"
                    "GHG: %{x:,.1f} tCO2e/yr<br>"
                    "Marine EP: %{marker.color:.3f} t N-eq/yr<br>"
                    "%{customdata[1]}<br>"
                    "<extra></extra>"
                ),
            )
        )
        fig.update_layout(
            xaxis_title="GHG emissions (tCO2e/yr)",
            yaxis_title="Annualized cost, NAC (M$/yr)",
            plot_bgcolor=SURFACE,
            paper_bgcolor=SURFACE,
            font=dict(color=INK_PRIMARY),
            xaxis=dict(gridcolor=GRIDLINE, zeroline=False),
            yaxis=dict(gridcolor=GRIDLINE, zeroline=False),
            margin=dict(t=20, b=10),
            height=480,
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "Lower-left is better on both axes shown, but cheaper almost always "
            "means more GHG allowed. That's the tradeoff, not a bug. Point size "
            "is constant; color shows the third objective (marine eutrophication)."
        )

        point_labels = scenario_df["Point"] + ": " + scenario_df["Config"].str.slice(0, 60)
        chosen = st.selectbox(
            "Select a point to inspect its technology blend",
            options=scenario_df["Point"],
            format_func=lambda p: point_labels[scenario_df["Point"] == p].iloc[0],
        )
        st.session_state["selected_point"] = chosen

    # -------------------------------------------------------------
    # Tab 2 — Technology blend for the selected point
    # -------------------------------------------------------------
    with tab_blend:
        chosen = st.session_state.get("selected_point", scenario_df["Point"].iloc[0])
        row = scenario_df[scenario_df["Point"] == chosen].iloc[0]

        st.subheader(f"Technology blend: {selected_scenario} / {chosen}")
        c1, c2, c3 = st.columns(3)
        c1.metric("NAC (M$/yr)", f"{row['NAC_MUSD_per_yr']:.3f}")
        c2.metric("GHG (tCO2e/yr)", f"{row['GHG_tCO2e_per_yr']:,.1f}")
        c3.metric("Marine EP (t N-eq/yr)", f"{row['EP_marine_tpy']:.3f}")
        st.caption(f"Solver status: {row.get('Quality', 'n/a')}")

        pct_cols = [c for c in scenario_df.columns if c.startswith("pct_") and "HTLrec" not in c and "GasUpg" not in c]
        tech_pct = {c.replace("pct_", ""): row[c] for c in pct_cols}
        tech_pct = {k: v for k, v in tech_pct.items() if v > 0.05}

        if tech_pct:
            techs = list(tech_pct.keys())
            fig2 = go.Figure(
                go.Bar(
                    x=[tech_pct[t] for t in techs],
                    y=[TECH_NAMES.get(t, t) for t in techs],
                    orientation="h",
                    marker_color=[TECH_COLOR.get(t, INK_MUTED) for t in techs],
                    text=[f"{tech_pct[t]:.1f}%" for t in techs],
                    textposition="outside",
                    hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
                )
            )
            fig2.update_layout(
                xaxis_title="Share of feed routed to this technology (%)",
                yaxis_title=None,
                plot_bgcolor=SURFACE,
                paper_bgcolor=SURFACE,
                font=dict(color=INK_PRIMARY),
                xaxis=dict(gridcolor=GRIDLINE, range=[0, max(tech_pct.values()) * 1.25]),
                margin=dict(t=20, b=10, l=10),
                height=90 + 50 * len(techs),
            )
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("No conversion-technology split recorded for this point.")

        with st.expander("Full configuration string (from the solver)"):
            st.code(row["Config"], language=None)

    # -------------------------------------------------------------
    # Tab — Cost breakdown: the cheapest route's NAC split into categories
    # -------------------------------------------------------------
    with tab_cost:
        if cost_df is None or selected_scenario not in set(cost_df["Scenario"]):
            st.info("Cost breakdown data isn't available for this scenario yet.")
        else:
            crow = cost_df[cost_df["Scenario"] == selected_scenario].iloc[0]
            cnac = crow["NAC_MUSD_per_yr"]

            corder = sorted(range(len(COST_COMPONENTS)), key=lambda i: crow[COST_COMPONENTS[i][2]])
            clabels = [COST_COMPONENTS[i][0] for i in corder]
            cvalues = [crow[COST_COMPONENTS[i][2]] for i in corder]
            ccolors = [COST_COMPONENTS[i][1] for i in corder]

            cfig = go.Figure(
                go.Bar(
                    x=cvalues,
                    y=clabels,
                    orientation="h",
                    marker_color=ccolors,
                    text=[f"${v:.2f}M ({v / cnac * 100:.0f}%)" for v in cvalues],
                    textposition="outside",
                    hovertemplate="%{y}: $%{x:.3f}M/yr<extra></extra>",
                )
            )
            cfig.update_layout(
                xaxis_title="Annualized cost (M$/yr)",
                yaxis_title=None,
                plot_bgcolor=SURFACE,
                paper_bgcolor=SURFACE,
                font=dict(color=INK_PRIMARY),
                xaxis=dict(gridcolor=GRIDLINE, zeroline=False, range=[0, max(cvalues) * 1.35]),
                yaxis=dict(gridcolor=GRIDLINE),
                margin=dict(t=20, b=10, l=10, r=20),
                height=360,
            )
            st.plotly_chart(cfig, width="stretch")
            st.caption(
                f"Total annualized cost (NAC) for {selected_scenario}'s cheapest "
                f"route: **${cnac:.2f}M/yr**."
            )

            ccols3 = st.columns(3)
            for i, (name, color, _key, desc) in enumerate(COST_COMPONENTS):
                with ccols3[i % 3]:
                    st.markdown(
                        f"""
                        <div style="border-left:4px solid {color};background:{SURFACE};
                                    border-radius:6px;padding:0.8em 1em;margin-bottom:0.8em;">
                          <div style="font-weight:700;color:{INK_PRIMARY};">{name}</div>
                          <div style="color:{INK_SECONDARY};font-size:0.88rem;">{desc}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            if is_placeholder:
                st.info(
                    "These numbers are placeholder estimates (the demo NAC split "
                    "by typical process-cost proportions), not the notebook's "
                    "real cost breakdown. Once your BARON solve exports the "
                    "actual capital, labor, and utility figures, drop them into "
                    "data/cost_breakdown.csv and this page updates automatically."
                )
            st.caption(
                "The model's underlying cost parameters (equipment cost, labor, "
                "utilities, product prices, disposal fees) are in Cost "
                "Specifications."
            )

    # -------------------------------------------------------------
    # Tab 3 — Compare scenarios (single min-NAC blend per scenario)
    # -------------------------------------------------------------
    with tab_compare:
        st.subheader("Cheapest blend, compared across all five feedstock scenarios")
        if comparison_df is not None:
            fig3 = go.Figure()
            fig3.add_trace(
                go.Bar(
                    x=comparison_df["Scenario"],
                    y=comparison_df["NAC_M$/yr"],
                    marker_color=CAT["blue"],
                    hovertemplate="%{x}<br>NAC: %{y:.3f} M$/yr<extra></extra>",
                    name="NAC",
                )
            )
            fig3.update_layout(
                yaxis_title="Annualized cost, NAC (M$/yr)",
                plot_bgcolor=SURFACE,
                paper_bgcolor=SURFACE,
                font=dict(color=INK_PRIMARY),
                yaxis=dict(gridcolor=GRIDLINE),
                margin=dict(t=20, b=10),
                height=380,
                showlegend=False,
            )
            st.plotly_chart(fig3, width="stretch")

            st.dataframe(
                comparison_df.rename(columns={
                    "NAC_M$/yr": "NAC (M$/yr)",
                    "GHG_tCO2e/yr": "GHG (tCO2e/yr)",
                    "EP_marine_tN-eq/yr": "Marine EP (t N-eq/yr)",
                }),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("scenario_comparison.csv not found. Add it to data/ to enable this view.")

    # -------------------------------------------------------------
    # Tab 4 — Feedstock characterization
    # -------------------------------------------------------------
    with tab_feedstock:
        st.subheader("Feed composition by source type")
        if feedstock_df is not None:
            show_cols = [c for c in feedstock_df.columns if c != "Scenario"]
            fdf = feedstock_df.set_index("Scenario")[show_cols]
            st.dataframe(fdf, width="stretch")

            metric = st.selectbox("Compare one property across scenarios", show_cols, index=0)
            fig4 = go.Figure(
                go.Bar(
                    x=fdf.index, y=fdf[metric],
                    marker_color=CAT["blue"],
                    hovertemplate="%{x}<br>" + metric + ": %{y}<extra></extra>",
                )
            )
            fig4.update_layout(
                yaxis_title=metric,
                plot_bgcolor=SURFACE,
                paper_bgcolor=SURFACE,
                font=dict(color=INK_PRIMARY),
                yaxis=dict(gridcolor=GRIDLINE),
                margin=dict(t=20, b=10),
                height=360,
            )
            st.plotly_chart(fig4, width="stretch")
        else:
            st.info("feedstock_composition.csv not found. Add it to data/ to enable this view.")

    # -------------------------------------------------------------
    # Tab 5 — Raw data + download
    # -------------------------------------------------------------
    with tab_data:
        st.subheader("All Pareto points")
        st.dataframe(pareto_df, width="stretch", hide_index=True)
        st.download_button(
            "Download filtered CSV",
            data=scenario_df.to_csv(index=False).encode("utf-8"),
            file_name=f"pareto_{selected_scenario.lower()}.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Dispatch — render whichever section is selected in the sidebar
# ---------------------------------------------------------------------------
if section == "Instructions":
    render_instructions()
elif section == "Feed Inputs":
    render_feed_inputs(scenarios, feedstock_df)
elif section == "Technology Specifications":
    render_technology_specifications()
elif section == "Cost Specifications":
    render_cost_specifications(cost_df, scenarios)
elif section == "Results":
    if results_subview is None:
        render_results_landing(RESULTS_SUBVIEWS)
    else:
        render_placeholder(results_subview)
elif section == "Environmental Justice":
    render_placeholder("Environmental Justice")