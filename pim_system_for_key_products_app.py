#!/usr/bin/env python
"""
PIM System Manager

This Streamlit app does the following:
  • Upload an input Excel file and an output CSV file.
  • The input file is filtered by:
       - "<Publication Link.|Node|.Description Level 02>"
       - "<Publication Link.|Node|.Description Level 03>"
       - "<Publication Link.|Node|.Description Level 04>"
     These three filters are applied sequentially so that the available “Catalog Description” 
     options are narrowed down accordingly.
  • Then you select one or more “Catalog Description” values (via a searchable, multiselect dropdown).
  • On clicking “Map and Append Selected Rows” each matching input row is processed.
     The following column mappings are applied:
         • "<Publication Link.|Node|.Description Level 02>" → "Product Group"
         • "<Publication Link.|Node|.Description Level 03>" → "Category"
         • "<Publication Link.|Node|.Description Level 04>" → "Series"
         • "Catalog Description" → "Name"
         • "Item Long Description" → "Description"
         • "Primary Image link" → "Featured image"
     All other columns are copied over – if the output CSV does not already have a column the row adds it (and a log is kept).
  • If any selected “Catalog Description” already exists in the output file, the differences (fields that differ)
     are shown and you may choose (via checkbox) whether to update the existing row.
  • Finally, the updated output is available for download as a CSV.
  
By default, the app is in wide mode.
"""

import streamlit as st
import pandas as pd
import io
import logging

# Set page config to wide mode.
st.set_page_config(page_title="PIM System Manager", layout="wide")

# Set up logging (for demonstration, we add messages to a list that is displayed in the app)
logging.basicConfig(level=logging.INFO)

# Define the input → output column mapping.
MAPPING = {
    "<Publication Link.|Node|.Description Level 02>": "Product Group",
    "<Publication Link.|Node|.Description Level 03>": "Category",
    "<Publication Link.|Node|.Description Level 04>": "Series",
    "Catalog Description": "Name",
    "Item Long Description": "Description",
    "Primary Image link": "Featured image"
}

# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_input_data(file_bytes):
    # Read the Excel file from bytes.
    return pd.read_excel(io.BytesIO(file_bytes))

@st.cache_data(show_spinner=False)
def load_output_data(file_bytes):
    # Read the CSV file from bytes.
    return pd.read_csv(io.BytesIO(file_bytes))

# ─────────────────────────────────────────────────────────────
def map_row(row):
    """
    Given a row (a pandas Series) from the input DataFrame,
    return a new Series with the mapped columns renamed.
    All other columns are kept.
    """
    new_row = row.copy()
    # For every mapping, set the target column.
    for src, tgt in MAPPING.items():
        new_row[tgt] = new_row[src]
    # Remove the input columns that were mapped.
    for src in MAPPING.keys():
        if src in new_row:
            new_row.pop(src)
    return new_row

# ─────────────────────────────────────────────────────────────
def compare_rows(existing_row, new_row):
    """
    Compare two rows (pandas Series) and return a dictionary of differences.
    The dict keys are column names and the value is a tuple (existing, new) if different.
    """
    diff = {}
    all_cols = set(existing_row.index).union(set(new_row.index))
    for col in all_cols:
        ex_val = existing_row.get(col, None)
        new_val = new_row.get(col, None)
        if pd.isna(ex_val) and pd.isna(new_val):
            continue
        if ex_val != new_val:
            diff[col] = (ex_val, new_val)
    return diff

# ─────────────────────────────────────────────────────────────
def add_missing_columns(df, new_row, log_list):
    """
    If any columns in new_row are missing from DataFrame df,
    add them (with default None) and log the change.
    """
    for col in new_row.index:
        if col not in df.columns:
            df[col] = None
            log_list.append(f"Added new column: {col}")
    return df

# ─────────────────────────────────────────────────────────────
def process_selected_rows(selected_df, df_output, auto_add_new, log_list):
    """
    Process and map every row in the filtered DataFrame.
    • For each row, call map_row().
    • If a row’s “Name” (from Catalog Description) is not in df_output, add it.
    • If it already exists, compare and store differences.
    
    Returns:
      df_output (updated),
      pending_updates: dictionary mapping product name to (existing_index, new_row, differences),
      log_list: list of log messages.
    """
    new_rows = []
    pending_updates = {}  # {Name: (existing_index, new_row, differences)}
    for idx, row in selected_df.iterrows():
        new_row = map_row(row)
        product_name = new_row.get("Name")
        if auto_add_new:
            df_output = add_missing_columns(df_output, new_row, log_list)
        # If output is empty or "Name" column does not exist, add row.
        if "Name" not in df_output.columns or df_output.empty:
            new_rows.append(new_row)
        else:
            existing_mask = df_output["Name"] == product_name
            if existing_mask.any():
                existing_index = df_output[existing_mask].index[0]
                existing_row = df_output.loc[existing_index]
                diff = compare_rows(existing_row, new_row)
                if diff:
                    pending_updates[product_name] = (existing_index, new_row, diff)
            else:
                new_rows.append(new_row)
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_output = pd.concat([df_output, df_new], ignore_index=True)
        log_list.append(f"Appended {len(new_rows)} new row(s) to output.")
    return df_output, pending_updates, log_list

# ─────────────────────────────────────────────────────────────
def main():
    st.title("PIM System Manager")
    st.write("Map and filter your input product Excel file to create a CSV output file for promotion items.")
    
    # ── SIDEBAR SELECTORS ─────────────────────────────────────────
    st.sidebar.header("File Selection")
    input_file = st.sidebar.file_uploader("Upload Input Excel File", type=["xlsx"])
    output_file = st.sidebar.file_uploader("Upload Output CSV File", type=["csv"])
    
    auto_add_new = st.sidebar.checkbox("Automatically add missing columns from input to output", value=True)
    
    # Initialize session state as needed.
    if "df_output" not in st.session_state:
        st.session_state.df_output = None
    if "pending_updates" not in st.session_state:
        st.session_state.pending_updates = {}
    if "process_logs" not in st.session_state:
        st.session_state.process_logs = []
    
    # ── LOAD AND CACHE INPUT FILE ──────────────────────────────────
    if input_file is not None:
        try:
            # Use caching: pass file bytes to the cached function.
            df_input = load_input_data(input_file.getvalue())
            st.write(f"Input file loaded: {len(df_input)} rows, {df_input.shape[1]} columns")
        except Exception as e:
            st.error("Error reading the input Excel file.")
            st.exception(e)
            return

        # Verify that required columns exist.
        required_cols = list(MAPPING.keys())
        missing_required = [col for col in required_cols if col not in df_input.columns]
        if missing_required:
            st.error(f"The input file is missing required columns: {missing_required}")
            return

        # ── CASCADING FILTERS ────────────────────────────────────────
        # First filter: Level 02.
        level02_options = sorted(df_input["<Publication Link.|Node|.Description Level 02>"].dropna().unique().tolist())
        level02_selected = st.multiselect("Filter by <Publication Link.|Node|.Description Level 02>", 
                                          options=level02_options,
                                          help="Leave unselected to include all.")

        # Start with a temporary filtered DataFrame.
        temp_df = df_input.copy()
        if level02_selected:
            temp_df = temp_df[temp_df["<Publication Link.|Node|.Description Level 02>"].isin(level02_selected)]

        # Second filter: Level 03.
        level03_options = sorted(temp_df["<Publication Link.|Node|.Description Level 03>"].dropna().unique().tolist())
        level03_selected = st.multiselect("Filter by <Publication Link.|Node|.Description Level 03>", 
                                          options=level03_options,
                                          help="Leave unselected to include all.")
        if level03_selected:
            temp_df = temp_df[temp_df["<Publication Link.|Node|.Description Level 03>"].isin(level03_selected)]

        # Third filter: Level 04.
        level04_options = sorted(temp_df["<Publication Link.|Node|.Description Level 04>"].dropna().unique().tolist())
        level04_selected = st.multiselect("Filter by <Publication Link.|Node|.Description Level 04>", 
                                          options=level04_options,
                                          help="Leave unselected to include all.")
        if level04_selected:
            temp_df = temp_df[temp_df["<Publication Link.|Node|.Description Level 04>"].isin(level04_selected)]

        # Fourth filter: Catalog Description.
        # The options are narrowed by the previously selected description levels.
        catalog_options = sorted(temp_df["Catalog Description"].dropna().unique().tolist())
        catalog_selected = st.multiselect("Select Catalog Description", options=catalog_options,
                                          help="Leave unselected to include all.")
        filtered_df = temp_df.copy()
        if catalog_selected:
            filtered_df = filtered_df[filtered_df["Catalog Description"].isin(catalog_selected)]

        st.subheader("Filtered Input Data")
        st.dataframe(filtered_df)

        # ── LOAD OR CREATE OUTPUT FILE ───────────────────────────────
        if output_file is not None:
            try:
                df_output = load_output_data(output_file.getvalue())
                st.write(f"Output CSV loaded: {len(df_output)} rows, {df_output.shape[1]} columns")
            except Exception as e:
                st.error("Error reading output CSV. A new output DataFrame will be created.")
                st.exception(e)
                df_output = pd.DataFrame()
        else:
            df_output = pd.DataFrame()
            st.info("No output file uploaded. A new output file will be created.")
        st.session_state.df_output = df_output

        # ── PROCESS THE SELECTED/FILTERED ROWS ───────────────────────
        if st.button("Map and Append Selected Rows"):
            if filtered_df.empty:
                st.warning("No rows match the selected filters.")
            else:
                process_logs = []
                updated_df, pending_updates, process_logs = process_selected_rows(filtered_df,
                                                                                  st.session_state.df_output,
                                                                                  auto_add_new,
                                                                                  process_logs)
                st.session_state.df_output = updated_df
                st.session_state.pending_updates = pending_updates
                st.session_state.process_logs = process_logs
                st.success("Mapping and appending completed.")
                st.subheader("Process Log")
                for log in process_logs:
                    st.text(log)

        # ── IF THERE ARE PENDING UPDATES ─────────────────────────────
        if st.session_state.pending_updates:
            st.subheader("Pending Updates (Existing products with differences)")
            update_choices = {}
            for product, (existing_index, new_row, differences) in st.session_state.pending_updates.items():
                with st.expander(f"Differences for product '{product}'"):
                    st.write("Differences (Column: (Existing, New)):")
                    st.write(differences)
                    update_choices[product] = st.checkbox(f"Update product '{product}' with new values?",
                                                            key=f"update_{product}")
            if st.button("Apply Updates for Existing Rows"):
                update_logs = []
                for prod, to_update in update_choices.items():
                    if to_update:
                        existing_index, new_row, differences = st.session_state.pending_updates[prod]
                        st.session_state.df_output = add_missing_columns(st.session_state.df_output, new_row, update_logs)
                        for col, val in new_row.items():
                            st.session_state.df_output.at[existing_index, col] = val
                        update_logs.append(f"Updated product '{prod}' with new values.")
                if update_logs:
                    st.session_state.process_logs.extend(update_logs)
                    st.success("Updates applied for selected existing rows.")
                    st.subheader("Update Log")
                    for log in update_logs:
                        st.text(log)
                else:
                    st.info("No existing rows were updated.")
                st.session_state.pending_updates = {}

        # ── SHOW FINAL OUTPUT AND OFFER CSV DOWNLOAD ───────────────
        if st.session_state.df_output is not None:
            st.subheader("Final Output Data")
            st.dataframe(st.session_state.df_output)
            csv_data = st.session_state.df_output.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Updated Output CSV",
                data=csv_data,
                file_name="updated_output.csv",
                mime="text/csv"
            )

if __name__ == '__main__':
    main()