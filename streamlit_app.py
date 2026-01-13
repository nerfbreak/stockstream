import streamlit as st
import pandas as pd
import zipfile

# --- Helper Functions ---
def load_data(file):
    # Cek jika file tidak ada
    if file is None:
        return None

    df = None
    filename = file.name.lower()

    # 1. CSV
    if filename.endswith('.csv'):
        try:
            # Coba delimiter TAB dulu (untuk INVT_MASTER)
            df = pd.read_csv(file, sep='\t')
            # Jika gagal (kolom <= 1), coba delimiter KOMA
            if df.shape[1] <= 1: 
                 file.seek(0)
                 df = pd.read_csv(file)
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            return None

    # 2. Excel
    elif filename.endswith(('.xls', '.xlsx')):
        try:
            df = pd.read_excel(file)
        except Exception as e:
            st.error(f"Error reading Excel: {e}")
            return None

    # 3. ZIP
    elif filename.endswith('.zip'):
        try:
            with zipfile.ZipFile(file) as z:
                target_filename = None
                
                # Cari file "INVT_MASTER"
                for name in z.namelist():
                    if "INVT_MASTER" in name and name.lower().endswith(".csv"):
                        target_filename = name
                        break
                
                # Jika tidak ketemu, ambil file CSV apa saja
                if target_filename is None:
                    for name in z.namelist():
                        if name.lower().endswith(".csv"):
                            target_filename = name
                            break
                
                if target_filename:
                    # Baca file dari dalam zip
                    with z.open(target_filename) as f:
                        # Asumsi INVT_MASTER pakai Tab Separator
                        df = pd.read_csv(f, sep='\t')
                else:
                    st.error("Tidak ditemukan file CSV di dalam file ZIP ini.")
                    return None
        except Exception as e:
            st.error(f"Gagal membaca file ZIP: {e}")
            return None
            
    return df

# --- Main App ---
st.set_page_config(page_title="Inventory Reconcile", layout="wide")
st.title("Inventory Reconcile")

# Upload
col1, col2 = st.columns(2)
with col1:
    # Ditambahkan type 'zip'
    file1 = st.file_uploader("Upload File Stock Newspage", type=['csv', 'xlsx', 'zip'])
    st.caption("Support: .csv, .xlsx, .zip (isi INVT_MASTER)")

with col2:
    file2 = st.file_uploader("Upload File Stock Distributor", type=['csv', 'xlsx'])

if file1 and file2:
    st.divider()
    
    # Load Data
    df1 = load_data(file1)
    df2 = load_data(file2)

    if df1 is not None and df2 is not None:
        
        # --- Konfigurasi Kolom ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Newspage")
            # Auto detect Newspage columns
            idx_sku1 = df1.columns.get_loc('Product Code') if 'Product Code' in df1.columns else 0
            idx_qty1 = df1.columns.get_loc('Stock Available') if 'Stock Available' in df1.columns else 1
            
            sku_col1 = st.selectbox("Kolom SKU (Newspage)", df1.columns, index=idx_sku1)
            qty_col1 = st.selectbox("Kolom Qty (Newspage)", df1.columns, index=idx_qty1)
        
        with c2:
            st.subheader("Distributor")
            # Default ke index kolom U (20) dan BT (71) untuk Report5010
            idx_sku2 = 20 if len(df2.columns) > 20 else 0
            idx_qty2 = 71 if len(df2.columns) > 71 else 1
            
            sku_col2 = st.selectbox("Kolom SKU (Distributor)", df2.columns, index=idx_sku2)
            qty_col2 = st.selectbox("Kolom Qty (Distributor)", df2.columns, index=idx_qty2)

        if st.button("Compare", type="primary"):
            # Proses Data Newspage
            d1 = df1[[sku_col1, qty_col1]].copy()
            d1[sku_col1] = d1[sku_col1].astype(str).str.strip()
            
            # --- FIX: Ensure Qty is Number ---
            d1[qty_col1] = pd.to_numeric(d1[qty_col1], errors='coerce').fillna(0)
            
            d1_agg = d1.groupby(sku_col1)[qty_col1].sum().reset_index()
            d1_agg.rename(columns={sku_col1: 'SKU', qty_col1: 'Newspage'}, inplace=True)

            # Proses Data Distributor
            d2 = df2[[sku_col2, qty_col2]].copy()
            d2[sku_col2] = d2[sku_col2].astype(str).str.strip()
            
            # --- FIX: Ensure Qty is Number ---
            d2[qty_col2] = pd.to_numeric(d2[qty_col2], errors='coerce').fillna(0)

            d2_agg = d2.groupby(sku_col2)[qty_col2].sum().reset_index()
            d2_agg.rename(columns={sku_col2: 'SKU', qty_col2: 'Distributor'}, inplace=True)

            # Merge
            merged = pd.merge(d1_agg, d2_agg, on='SKU', how='outer', indicator=True)
            merged[['Newspage', 'Distributor']] = merged[['Newspage', 'Distributor']].fillna(0)
            
            # Hitung Selisih (Distributor - Newspage)
            merged['Selisih'] = merged['Distributor'] - merged['Newspage']
            
            # Status Simpel
            merged['Status'] = merged['Selisih'].apply(lambda x: 'Match' if x == 0 else 'Mismatch')

            # Tampilkan Hasil
            st.success("Results")
            
            # Metric Ringkas
            m1, m2 = st.columns(2)
            m1.metric("Total Match", len(merged[merged['Selisih'] == 0]))
            m2.metric("Total Mismatch", len(merged[merged['Selisih'] != 0]), delta_color="inverse")
            
            # Filter Mismatch
            mismatches = merged[merged['Selisih'] != 0].sort_values('Selisih')
            
            st.subheader("Detail Stock Selisih (Mismatch)")
            st.dataframe(
                mismatches[['SKU', 'Newspage', 'Distributor', 'Selisih', 'Status']],
                use_container_width=True,
                hide_index=True
            )

            # Download Button
            csv_data = merged[['SKU', 'Newspage', 'Distributor', 'Selisih', 'Status']].to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name="selisih_stock.csv",
                mime="text/csv"
            )
