import streamlit as st
import pandas as pd
import zipfile

# --- Helper ---
def load_data(file):
    if file is None: return None
    df = None
    filename = file.name.lower()

    # 1. CSV
    if filename.endswith('.csv'):
        try:
            # Delimiter Tab
            df = pd.read_csv(file, sep='\t', dtype=str) 
            if df.shape[1] <= 1: 
                 file.seek(0)
                 df = pd.read_csv(file, sep=',', dtype=str)
        except Exception as e:
            file.seek(0)
            try:
                df = pd.read_csv(file, dtype=str)
            except:
                st.error(f"Error baca CSV: {e}")
                return None

    # 2. Excel
    elif filename.endswith(('.xls', '.xlsx')):
        try:
            df = pd.read_excel(file, dtype=str)
        except Exception as e:
            st.error(f"Error baca Excel: {e}")
            return None

    # 3. ZIP
    elif filename.endswith('.zip'):
        try:
            with zipfile.ZipFile(file) as z:
                target_filename = None
                for name in z.namelist():
                    if "INVT_MASTER" in name and name.lower().endswith(".csv"):
                        target_filename = name
                        break
                if target_filename is None:
                    for name in z.namelist():
                        if name.lower().endswith(".csv"):
                            target_filename = name
                            break
                if target_filename:
                    with z.open(target_filename) as f:
                        df = pd.read_csv(f, sep='\t', dtype=str)
                else:
                    st.error("CSV Not Found.")
                    return None
        except Exception as e:
            st.error(f"Fail Read Zip: {e}")
            return None
            
    return df

# --- App ---
st.set_page_config(page_title="Inventory Reconcile", layout="wide")
st.title("Inventory Reconcile")

# Upload
col1, col2 = st.columns(2)
with col1:
    file1 = st.file_uploader("Upload File Stock Newspage", type=['csv', 'xlsx', 'zip'])

with col2:
    file2 = st.file_uploader("Upload File Stock Distributor", type=['csv', 'xlsx'])

if file1 and file2:
    st.divider()
    
    df1 = load_data(file1)
    df2 = load_data(file2)

    if df1 is not None and df2 is not None:
        
        # --- Config Kolom ---
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Newspage")
            idx_sku1 = df1.columns.get_loc('Product Code') if 'Product Code' in df1.columns else 0
            idx_qty1 = df1.columns.get_loc('Stock Available') if 'Stock Available' in df1.columns else 1
            sku_col1 = st.selectbox("Kolom SKU (Newspage)", df1.columns, index=idx_sku1)
            qty_col1 = st.selectbox("Kolom Qty (Newspage)", df1.columns, index=idx_qty1)
        
        with c2:
            st.subheader("Distributor")
            idx_sku2 = 20 if len(df2.columns) > 20 else 0
            idx_qty2 = 71 if len(df2.columns) > 71 else 1
            sku_col2 = st.selectbox("Kolom SKU (Distributor)", df2.columns, index=idx_sku2)
            qty_col2 = st.selectbox("Kolom Qty (Distributor)", df2.columns, index=idx_qty2)

        if st.button("Compare", type="primary"):
            # 1. Proses Newspage
            d1 = df1[[sku_col1, qty_col1]].copy()
            # Hapus desimal .0
            d1[sku_col1] = d1[sku_col1].astype(str).str.split('.').str[0].str.strip()
            d1[qty_col1] = pd.to_numeric(d1[qty_col1], errors='coerce').fillna(0)
            d1_agg = d1.groupby(sku_col1)[qty_col1].sum().reset_index().rename(columns={sku_col1: 'SKU', qty_col1: 'Newspage'})

            # 2. Proses Distributor
            d2 = df2[[sku_col2, qty_col2]].copy()
            # CLear Data
            d2[sku_col2] = d2[sku_col2].astype(str).str.split('.').str[0].str.strip()
            
            # --- AUTO FIX SKU ---
            d2[sku_col2] = d2[sku_col2].replace({
                '373103': '0373103',
                '373100': '0373100'
            })
            # --------------------
            
            d2[qty_col2] = pd.to_numeric(d2[qty_col2], errors='coerce').fillna(0)
            d2_agg = d2.groupby(sku_col2)[qty_col2].sum().reset_index().rename(columns={sku_col2: 'SKU', qty_col2: 'Distributor'})

            # 3. Merge
            merged = pd.merge(d1_agg, d2_agg, on='SKU', how='outer', indicator=True)
            merged[['Newspage', 'Distributor']] = merged[['Newspage', 'Distributor']].fillna(0)
            merged['Selisih'] = merged['Distributor'] - merged['Newspage']
            merged['Status'] = merged['Selisih'].apply(lambda x: 'Match' if x == 0 else 'Mismatch')

            # --- SHow result ---
            st.success("Results")
            
            # Metric
            m1, m2 = st.columns(2)
            m1.metric("Total Match", len(merged[merged['Selisih'] == 0]))
            m2.metric("Total Mismatch", len(merged[merged['Selisih'] != 0]), delta_color="inverse")

            # Tabel Detail Selisih
            st.subheader("Detail Stock Selisih (Mismatch)")
            mismatches = merged[merged['Selisih'] != 0].sort_values('Selisih')
            
            st.dataframe(
                mismatches[['SKU', 'Newspage', 'Distributor', 'Selisih', 'Status']],
                use_container_width=True,
                hide_index=True
            )

            # Download CSV
            csv_data = merged[['SKU', 'Newspage', 'Distributor', 'Selisih', 'Status']].to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv_data, "reconcile_full.csv", "text/csv")
