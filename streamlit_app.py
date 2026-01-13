import streamlit as st
import pandas as pd

# --- Helper Functions ---
def load_data(file):
    if file.name.endswith('.csv'):
        try:
            df = pd.read_csv(file, sep='\t')
            if df.shape[1] <= 1: 
                 file.seek(0)
                 df = pd.read_csv(file)
        except:
            file.seek(0)
            df = pd.read_csv(file)
    elif file.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file)
    else:
        return None
    return df

# --- Main App ---
st.title("Invetory Reconcile")

# Upload
col1, col2 = st.columns(2)
with col1:
    file1 = st.file_uploader("Upload File Stock Newspage", type=['csv', 'xlsx'])
with col2:
    file2 = st.file_uploader("Upload File Stock Distributor", type=['csv', 'xlsx'])

if file1 and file2:
    st.divider()
    df1 = load_data(file1)
    df2 = load_data(file2)

    if df1 is not None and df2 is not None:
        # Pilihan Kolom (Tanpa Deskripsi)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Newspage")
            sku_col1 = st.selectbox("Kolom SKU (Newspage)", df1.columns, index=df1.columns.get_loc('Product Code') if 'Product Code' in df1.columns else 0)
            qty_col1 = st.selectbox("Kolom Qty (Newspage)", df1.columns, index=df1.columns.get_loc('Stock Available') if 'Stock Available' in df1.columns else 1)
        
        with c2:
            st.subheader("Distributor")
            # Default ke index kolom U (20) dan BT (71) jika ada
            idx_sku2 = 20 if len(df2.columns) > 20 else 0
            idx_qty2 = 71 if len(df2.columns) > 71 else 1
            sku_col2 = st.selectbox("Kolom SKU (Distributor)", df2.columns, index=idx_sku2)
            qty_col2 = st.selectbox("Kolom Qty (Distributor)", df2.columns, index=idx_qty2)

        if st.button("Compare"):
            # Proses Data Newspage
            d1 = df1[[sku_col1, qty_col1]].copy()
            d1[sku_col1] = d1[sku_col1].astype(str).str.strip()
            d1_agg = d1.groupby(sku_col1)[qty_col1].sum().reset_index()
            d1_agg.rename(columns={sku_col1: 'SKU', qty_col1: 'Newspage'}, inplace=True)

            # Proses Data Distributor
            d2 = df2[[sku_col2, qty_col2]].copy()
            d2[sku_col2] = d2[sku_col2].astype(str).str.strip()
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
            st.success("Done")
            
            # Filter Mismatch
            mismatches = merged[merged['Selisih'] != 0].sort_values('Selisih')
            
            st.subheader("Detail Stock Selisih")
            st.dataframe(mismatches[['SKU', 'Newspage', 'Distributor', 'Selisih', 'Status']])

            # Download
            csv = merged[['SKU', 'Newspage', 'Distributor', 'Selisih', 'Status']].to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "hasil_selisih_stock.csv", "text/csv")
