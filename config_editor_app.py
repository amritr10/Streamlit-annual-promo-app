import streamlit as st
import pandas as pd
import json
import os

# Configure Streamlit page before any other Streamlit commands
st.set_page_config(page_title="Spec View Config Editor", layout="wide")

# -- UI custom CSS for expanders
st.markdown(
    """
    <style>
    /* Existing config expanders */
    .existing-expander > .streamlit-expanderHeader {
        background-color: #f5f5f5 !important;
    }
    /* New config expander */
    .new-expander > .streamlit-expanderHeader {
        background-color: #d4f4dd !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------- CONFIGURATION -------------------------
CONFIG_FILE_PATH = os.path.join("spec_view_configs", "spec_view_configs.json")
PRODUCTS_CSV_PATH = "merged_eu_pim_with_key_products.csv"

# ------------------------- HELPER FUNCTIONS -------------------------

def load_config():
    """Loads the spec view configuration from the JSON file."""
    if os.path.exists(CONFIG_FILE_PATH):
        with open(CONFIG_FILE_PATH, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    """Saves the configuration data to the JSON file."""
    with open(CONFIG_FILE_PATH, "w") as f:
        json.dump(data, f, indent=4)

def load_product_data():
    """Loads the product data from the CSV file."""
    if os.path.exists(PRODUCTS_CSV_PATH):
        return pd.read_csv(PRODUCTS_CSV_PATH)
    return pd.DataFrame()

# ------------------------- UI FOR CONFIGURATION FORM -------------------------
def configuration_form(df, existing_config=None, key_suffix=""):
    """Renders the form for creating or editing a configuration."""
    st.subheader("Configuration Details")

    # Ensure existing_config is a dictionary
    existing_config = existing_config or {}

    # --- Get available spec columns for the selected series ---
    spec_columns = sorted([col for col in df.columns if ";" in col and df[col].notna().any()])
    series_options = sorted(df["Series"].dropna().unique())

    # --- Series selection logic ---
    # Determine default series using existing config and global toggle
    default_series = existing_config.get("series", [])
    if not default_series and select_all_series_global:
        default_series = series_options

    # Form fields organized in two columns
    col1, col2 = st.columns(2)
    with col1:
        selected_series = st.multiselect("Series", options=series_options, default=default_series, key=f"series_{key_suffix}")
        if not selected_series:
            st.warning("Please select at least one series.")
            st.stop()
        group_by_cols = st.multiselect("Group By Columns", options=spec_columns, default=existing_config.get("group_by_cols", []), key=f"group_by_{key_suffix}")

    with col2:
        display_col_options = ["None"] + spec_columns
        default_display_col = existing_config.get("display_col") if existing_config.get("display_col") in display_col_options else "None"
        display_col = st.selectbox("Display Column (Optional)", options=display_col_options, index=display_col_options.index(default_display_col), key=f"display_col_{key_suffix}")
        pivot_required = st.checkbox("Requires Pivot View?", value=existing_config.get("pivot_required", False), key=f"pivot_req_{key_suffix}")
        if pivot_required:
            pivot_col_options = spec_columns
            default_pivot_col = existing_config.get("pivot_col") if existing_config.get("pivot_col") in pivot_col_options else None
            pivot_col = st.selectbox("Pivot Column", options=pivot_col_options, index=pivot_col_options.index(default_pivot_col) if default_pivot_col else 0, key=f"pivot_col_{key_suffix}")
            pivot_value_col = "Name"
        else:
            pivot_col = None
            pivot_value_col = None

    # --- Save Button ---
    if st.button("Save Configuration", key=f"save_{key_suffix}"):
        new_config = {
            "series": selected_series,
            "group_by_cols": group_by_cols,
            "display_col": display_col if display_col != "None" else None,
            "pivot_required": pivot_required,
            "pivot_col": pivot_col,
            "pivot_value_col": pivot_value_col
        }
        return new_config
    return None

# ------------------------- MAIN APP -------------------------
# set_page_config moved to top
st.title("BACKEND:Specification View Configuration Editor")

# --- Load Data ---
config_data = load_config()
df = load_product_data()

if df.empty:
    st.error(f"Product data not found at '{PRODUCTS_CSV_PATH}'. Please ensure the file exists.")
    st.stop()

# --- Main Area for Creating/Editing Configurations ---
st.header("Create or Update a Configuration")

# --- Sidebar Controls for Product Selection and Defaults ---
st.sidebar.header("Controls")
product_group_options = sorted(df["Product Group"].dropna().unique())
selected_product_group = st.sidebar.selectbox("Product Group", options=product_group_options)
select_all_series_global = st.sidebar.checkbox("Select all series by default", value=False)

if selected_product_group:
    if selected_product_group not in config_data:
        config_data[selected_product_group] = {"series_configs": []}

    # Organize into tabs
    tabs = st.tabs(["✏️ Existing Configurations", "➕ New Configuration"])

    # Tab 1: Existing Configurations
    with tabs[0]:
        st.subheader(f"Existing Configurations for {selected_product_group}")
        for i, config in enumerate(config_data[selected_product_group]["series_configs"]):
            st.markdown('<div class="existing-expander">', unsafe_allow_html=True)
            with st.expander(f"✏️ Configuration for Series: {', '.join(config['series'])}"):
                edited_config = configuration_form(
                    df[df["Product Group"] == selected_product_group],
                    existing_config=config,
                    key_suffix=f"edit_{i}"
                )
                if edited_config:
                    config_data[selected_product_group]["series_configs"][i] = edited_config
                    save_config(config_data)
                    st.success("Configuration updated!")
                    st.rerun()

                # Delete option
                st.markdown("---")
                st.warning("Danger Zone: Delete this configuration")
                confirm_delete = st.checkbox(
                    f"Confirm delete configuration {i+1}", key=f"confirm_delete_{i}"
                )
                if st.button("Delete Configuration", key=f"delete_{i}"):
                    if confirm_delete:
                        del config_data[selected_product_group]["series_configs"][i]
                        save_config(config_data)
                        st.success("Configuration deleted.")
                        st.rerun()
                    else:
                        st.warning("Please confirm deletion by checking the box.")
            st.markdown('</div>', unsafe_allow_html=True)

    # Tab 2: New Configuration
    with tabs[1]:
        st.subheader("Create New Configuration")
        st.markdown('<div class="new-expander">', unsafe_allow_html=True)
        with st.expander("➕ Create a new configuration for this product group"):
            new_config = configuration_form(
                df[df["Product Group"] == selected_product_group], key_suffix="new"
            )
            if new_config:
                config_data[selected_product_group]["series_configs"].append(new_config)
                save_config(config_data)
                st.success("New configuration created!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

