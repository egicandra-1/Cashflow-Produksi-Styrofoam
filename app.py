import streamlit as st
import pandas as pd
import time
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import streamlit.components.v1 as components
import threading
import os
import urllib.request

# --- KAMUS HARI BAHASA INDONESIA ---
HARI_INDO = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
}
URUTAN_HARI = {"Senin": 1, "Selasa": 2, "Rabu": 3, "Kamis": 4, "Jumat": 5, "Sabtu": 6, "Minggu": 7}

st.set_page_config(page_title="Aplikasi Cashflow Styrofoam", layout="centered", page_icon="📦")

# ==========================================
# MENGUNDUH FONT AGAR INVOICE RAPI DI CLOUD
# ==========================================
@st.cache_resource
def setup_fonts():
    fonts = {
        "Roboto-Regular.ttf": "https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf",
        "Roboto-Bold.ttf": "https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Bold.ttf"
    }
    for fname, url in fonts.items():
        if not os.path.exists(fname):
            try:
                urllib.request.urlretrieve(url, fname)
            except:
                pass
setup_fonts()

# ==========================================
# SUNTIKAN CSS: MEMBERSIHKAN UI & TABEL
# ==========================================
st.markdown("""
    <style>
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    header {display: none !important;}
    .stDeployButton {display: none !important;}
    </style>
""", unsafe_allow_html=True)

st.title("Aplikasi Cashflow Styrofoam")

# ==========================================
# FUNGSI MENARIK & MENYIMPAN DATA (DILENGKAPI BACKUP LOKAL ANTI-HILANG)
# ==========================================
def load_cloud_data():
    df_n = pd.DataFrame()
    df_l = pd.DataFrame()
    
    # Mencoba menarik dari Cloud (Google Sheets)
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
        client = gspread.authorize(creds)
        
        # Otomatis buat file g-sheet jika terhapus/belum ada agar tidak error
        try:
            ss = client.open("Cashflow Styrofoam")
        except:
            ss = client.create("Cashflow Styrofoam")
        
        try:
            df_n = pd.DataFrame(ss.worksheet("Data_Nota").get_all_records())
        except:
            pass
            
        try:
            df_l = pd.DataFrame(ss.worksheet("Data_Pengeluaran_Lain").get_all_records())
        except:
            pass
    except Exception:
        pass
        
    # BACKUP LAYER: Jika gagal/kosong dari Cloud, panggil file CSV internal (Anti-hilang saat Refresh)
    if df_n.empty and os.path.exists("backup_nota.csv"):
        try: df_n = pd.read_csv("backup_nota.csv")
        except: pass
        
    if df_l.empty and os.path.exists("backup_lain.csv"):
        try: df_l = pd.read_csv("backup_lain.csv")
        except: pass
        
    return df_n, df_l

def background_sync(df, sheet_name="Data_Nota"):
    # 1. SIMPAN KE PENYIMPANAN SERVER INTERNAL (Instan & Pasti Aman dari Refresh)
    backup_name = "backup_nota.csv" if "Nota" in sheet_name else "backup_lain.csv"
    try:
        df.to_csv(backup_name, index=False)
    except:
        pass

    # 2. SIMPAN KE CLOUD GOOGLE SHEETS (Di Latar Belakang agar tidak loading lama)
    def task():
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            
            if "gcp_service_account" in st.secrets:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            else:
                creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
                
            client = gspread.authorize(creds)
            try:
                ss = client.open("Cashflow Styrofoam")
            except:
                ss = client.create("Cashflow Styrofoam")
                
            try:
                ws = ss.worksheet(sheet_name)
            except:
                ws = ss.add_worksheet(title=sheet_name, rows="100", cols="15")
                
            ws.clear()
            if not df.empty:
                df_clean = df.fillna("")
                ws.append_row(df_clean.columns.tolist())
                ws.append_rows(df_clean.values.tolist())
        except Exception:
            pass
            
    # Menggunakan thread normal agar tidak ter-kill oleh server di tengah jalan
    threading.Thread(target=task).start()

# ==========================================
# INISIALISASI MEMORI (TARIK DATA DARI CLOUD / BACKUP SAAT DIBUKA)
# ==========================================
if 'data_loaded' not in st.session_state:
    df_nota_cloud, df_lain_cloud = load_cloud_data()
    
    if not df_nota_cloud.empty:
        st.session_state.df_nota = df_nota_cloud
    else:
        st.session_state.df_nota = pd.DataFrame(columns=[
            "ID Data", "Hari", "Tanggal", "Jenis Pekerjaan", "Harga Satuan", "Jumlah (pcs)", "Subtotal", "Status Pengiriman", "Potongan Ongkir", "Tambahan Ongkir", "Total Bersih"
        ])
        
    if not df_lain_cloud.empty:
        st.session_state.df_lain = df_lain_cloud
    else:
        st.session_state.df_lain = pd.DataFrame(columns=["ID Lain", "Hari", "Tanggal", "Jenis", "Keterangan", "Nominal"])
        
    st.session_state.data_loaded = True

if 'pengaturan_pekerjaan' not in st.session_state or st.session_state['pengaturan_pekerjaan'].empty:
    st.session_state['pengaturan_pekerjaan'] = pd.DataFrame({
        'Jenis Pekerjaan': ['KUMPLIT', 'POLOS'],
        'Harga Satuan (Rp)': [195, 150]
    })

if 'form_counter' not in st.session_state:
    st.session_state.form_counter = 0

if 'form_counter_lain' not in st.session_state:
    st.session_state.form_counter_lain = 0

# ==========================================
# PEMBUATAN TAB MENU UTAMA
# ==========================================
menu1, menu2, menu3, menu4, menu5 = st.tabs([
    "📝 Input Cepat", 
    "🗃️ Database Nota", 
    "💸 Pengeluaran/Penambahan", 
    "🖨️ Cetak Invoice", 
    "⚙️ Pengaturan"
])

# ==========================================
# MENU 1: INPUT CEPAT
# ==========================================
with menu1:
    st.header("Input Data Nota")
    
    df_pek = st.session_state['pengaturan_pekerjaan']
    if df_pek.empty:
        st.warning("⚠️ Data Jenis Pekerjaan kosong! Silakan isi terlebih dahulu di Menu Pengaturan.")
    else:
        today_date = datetime.today().date()
        if "last_date_input" not in st.session_state:
            st.session_state.last_date_input = today_date

        with st.container(border=True):
            tanggal = st.date_input("Tanggal", st.session_state.last_date_input, max_value=datetime.today(), format="DD/MM/YYYY", key=f"tgl_{st.session_state.form_counter}")
            
            st.write("")
            st.markdown("**Rincian Pekerjaan**")
            
            col_h1, col_h2 = st.columns([2, 1])
            with col_h1: st.caption("Jenis Pekerjaan")
            with col_h2: st.caption("Jumlah (Pcs)")
            
            input_pcs = {}
            for idx, row in df_pek.iterrows():
                jenis = row['Jenis Pekerjaan']
                harga = float(row['Harga Satuan (Rp)'])
                
                col_lbl, col_val = st.columns([2, 1])
                with col_lbl:
                    st.markdown(f"**{jenis}** *(Rp {harga:,.0f})*".replace(",", "."))
                with col_val:
                    input_pcs[jenis] = st.text_input(f"qty_{jenis}", value="", placeholder="0", label_visibility="collapsed", key=f"qty_{jenis}_{st.session_state.form_counter}")

            st.write("")
            st.markdown("**Status Pengiriman**")
            status_kirim = st.radio(
                "Pilih Status",
                ["Diambil", "Dikirim", "Subsidi Ongkir"],
                horizontal=True,
                label_visibility="collapsed",
                key=f"status_kirim_radio_{st.session_state.form_counter}"
            )
            
            nominal_ongkir_str = ""
            if status_kirim in ["Diambil", "Subsidi Ongkir"]:
                st.write("")
                label_ongkir = "Nominal Potongan Ongkir (Input Sendiri)" if status_kirim == "Diambil" else "Nominal Subsidi Ongkir (Input Sendiri)"
                st.markdown(f"**{label_ongkir}**")
                nominal_ongkir_str = st.text_input("ongkir_val", value="", placeholder="0", label_visibility="collapsed", key=f"ongkir_val_{st.session_state.form_counter}")

            st.write("")
            
            notif_area = st.empty()
            if "notif_msg" in st.session_state:
                if st.session_state.notif_type == "success":
                    notif_area.success(st.session_state.notif_msg)
                else:
                    notif_area.error(st.session_state.notif_msg)
                time.sleep(3)
                notif_area.empty()
                del st.session_state.notif_msg
                del st.session_state.notif_type

            btn_save = st.button("Simpan/Save", type="primary", use_container_width=True)

        if btn_save:
            st.session_state.last_date_input = tanggal
            nama_hari = HARI_INDO[tanggal.strftime("%A")]
            
            pekerjaan_dikerjakan = []
            for jenis, val_str in input_pcs.items():
                clean_val = val_str.strip()
                qty = int(clean_val) if clean_val.isdigit() else 0
                if qty > 0:
                    harga = float(df_pek.loc[df_pek['Jenis Pekerjaan'] == jenis, 'Harga Satuan (Rp)'].values[0])
                    pekerjaan_dikerjakan.append({
                        "jenis": jenis,
                        "harga": harga,
                        "qty": qty,
                        "subtotal": qty * harga
                    })
            
            if not pekerjaan_dikerjakan:
                st.session_state.notif_msg = "⚠️ Gagal! Mohon isi minimal 1 jumlah pekerjaan (pcs)."
                st.session_state.notif_type = "error"
                st.rerun()
            
            clean_ongkir = nominal_ongkir_str.strip() if nominal_ongkir_str else ""
            nominal_ongkir = int(clean_ongkir) if clean_ongkir.isdigit() else 0

            if status_kirim in ["Diambil", "Subsidi Ongkir"] and (not clean_ongkir or nominal_ongkir <= 0):
                label_nama_ongkir = "Potongan Ongkir" if status_kirim == "Diambil" else "Subsidi Ongkir"
                st.session_state.notif_msg = f"⚠️ Gagal Disimpan! Mohon isi nominal {label_nama_ongkir} terlebih dahulu."
                st.session_state.notif_type = "error"
                st.rerun()

            tgl_str = tanggal.strftime("%Y-%m-%d")
            
            baris_baru_list = []
            total_semua_bersih = 0
            
            for i, item in enumerate(pekerjaan_dikerjakan):
                id_data = f"NOTA-{int(time.time()*1000)}-{i}"
                
                pot_ongkir = nominal_ongkir if (status_kirim == "Diambil" and i == 0) else 0
                tam_ongkir = nominal_ongkir if (status_kirim == "Subsidi Ongkir" and i == 0) else 0
                total_bersih = item["subtotal"] - pot_ongkir + tam_ongkir
                
                total_semua_bersih += total_bersih
                
                baris_baru_list.append({
                    "ID Data": id_data,
                    "Hari": nama_hari,
                    "Tanggal": tgl_str,
                    "Jenis Pekerjaan": item["jenis"],
                    "Harga Satuan": item["harga"],
                    "Jumlah (pcs)": item["qty"],
                    "Subtotal": item["subtotal"],
                    "Status Pengiriman": status_kirim,
                    "Potongan Ongkir": pot_ongkir,
                    "Tambahan Ongkir": tam_ongkir,
                    "Total Bersih": total_bersih
                })
            
            df_baru = pd.DataFrame(baris_baru_list)
            st.session_state.df_nota = pd.concat([st.session_state.df_nota, df_baru], ignore_index=True)
            background_sync(st.session_state.df_nota, "Data_Nota")
            
            total_rp_str = f"Rp {total_semua_bersih:,.0f}".replace(",", ".")
            st.session_state.notif_msg = f"✅ TERSIMPAN! Total Bersih: {total_rp_str}"
            st.session_state.notif_type = "success"
            
            st.session_state.form_counter += 1
            st.rerun()

        components.html("""
        <script>
        const doc = window.parent.document;
        if (!doc.getElementById('custom-enter-save-script')) {
            doc.body.insertAdjacentHTML('beforeend', '<div id="custom-enter-save-script" style="display:none;"></div>');
            doc.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    const active = doc.activeElement;
                    if (active && active.tagName === 'INPUT' && (active.type === 'text' || active.type === 'number')) {
                        const btns = Array.from(doc.querySelectorAll('button'));
                        const saveBtn = btns.find(b => b.innerText.trim() === 'Simpan/Save' && b.offsetParent !== null);
                        if (saveBtn) {
                            e.preventDefault();
                            e.stopPropagation();
                            saveBtn.focus();
                            setTimeout(() => { saveBtn.click(); }, 50);
                        }
                    }
                }
            }, true);
        }
        </script>
        """, height=0, width=0)

# ==========================================
# MENU 2: DATABASE NOTA
# ==========================================
with menu2:
    st.header("Database Riwayat Pengiriman")
    st.caption("💡 Pilih rentang tanggal pada kalender untuk melihat data periode tertentu. Centang kotak di kiri tabel lalu tekan ikon hapus untuk menghapus baris.")

    df_nota = st.session_state.df_nota.copy()
    if len(df_nota) > 0:
        df_nota['Date_Obj'] = pd.to_datetime(df_nota['Tanggal']).dt.date
        max_tgl = df_nota['Date_Obj'].max()
        min_tgl = df_nota['Date_Obj'].min()
        
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            rentang_tanggal = st.date_input("Pilih Periode Tanggal", value=(min_tgl, max_tgl), max_value=datetime.today().date(), format="DD/MM/YYYY")
        with col_f2:
            opsi_pekerjaan_db = ["Semua Pekerjaan"] + df_nota['Jenis Pekerjaan'].unique().tolist()
            filter_pek = st.selectbox("🔍 Filter Jenis Pekerjaan:", opsi_pekerjaan_db)
            
        if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
            tgl_mulai, tgl_selesai = rentang_tanggal
        else:
            tgl_mulai = tgl_selesai = rentang_tanggal[0] if isinstance(rentang_tanggal, tuple) else rentang_tanggal

        df_tampil = df_nota[(df_nota['Date_Obj'] >= tgl_mulai) & (df_nota['Date_Obj'] <= tgl_selesai)].copy()
        if filter_pek != "Semua Pekerjaan":
            df_tampil = df_tampil[df_tampil['Jenis Pekerjaan'] == filter_pek]
            
        if len(df_tampil) > 0:
            df_tampil['Urutan_Hari'] = df_tampil['Hari'].map(URUTAN_HARI).fillna(8)
            df_tampil = df_tampil.sort_values(by=["Tanggal", "Urutan_Hari"], ascending=[False, True]).drop(columns=["Urutan_Hari", "Date_Obj"])
            
            daftar_tanggal = df_tampil[['Tanggal', 'Hari']].drop_duplicates().values
            
            for tgl, hari in daftar_tanggal:
                tgl_format = datetime.strptime(str(tgl), "%Y-%m-%d").strftime("%d-%m-%Y")
                with st.expander(f"📅 Hari **{hari}**, **{tgl_format}**", expanded=True):
                    df_harian = df_tampil[(df_tampil['Tanggal'] == tgl) & (df_tampil['Hari'] == hari)].copy()
                    
                    df_harian_view = df_harian[['ID Data', 'Jenis Pekerjaan', 'Harga Satuan', 'Jumlah (pcs)', 'Subtotal', 'Status Pengiriman']].copy().reset_index(drop=True)
                    
                    for col_num in ['Harga Satuan', 'Jumlah (pcs)', 'Subtotal']:
                        df_harian_view[col_num] = pd.to_numeric(df_harian_view[col_num], errors='coerce').fillna(0)
                        
                    total_harian_bersih = pd.to_numeric(df_harian['Total Bersih'], errors='coerce').fillna(0).sum()
                    
                    edited_df = st.data_editor(
                        df_harian_view,
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "ID Data": None,
                            "Harga Satuan": st.column_config.NumberColumn(format="Rp %,d"),
                            "Subtotal": st.column_config.NumberColumn(format="Rp %,d"),
                            "Jumlah (pcs)": st.column_config.NumberColumn(format="%,d")
                        },
                        key=f"editor_nota_{tgl}_{hari}"
                    )
                    
                    st.markdown(f"🔹 **Total Bersih Hari Ini ({tgl_format}):** `Rp {total_harian_bersih:,.0f}`".replace(",", "."))
                    
                    orig_ids = set(df_harian_view['ID Data'].dropna().tolist())
                    current_ids = set(edited_df['ID Data'].dropna().tolist())
                    deleted_ids = list(orig_ids - current_ids)
                    
                    if deleted_ids:
                        st.session_state.df_nota = st.session_state.df_nota[~st.session_state.df_nota['ID Data'].isin(deleted_ids)]
                        background_sync(st.session_state.df_nota, "Data_Nota")
                        st.success("✅ Data berhasil dihapus!")
                        st.rerun()
        else:
            st.info("Tidak ada data pengiriman pada rentang tanggal atau filter tersebut.")
    else:
        st.info("Belum ada data transaksi yang tercatat.")

# ==========================================
# MENU 3: PENGELUARAN / PENAMBAHAN LAIN
# ==========================================
with menu3:
    st.header("Pencatatan Pengeluaran / Penambahan Lain")
    st.caption("💡 Masukkan sisa nota, penyesuaian, atau pengeluaran fleksibel lainnya dengan memilih jenis Penambahan atau Pengurangan.")
    
    today_date_lain = datetime.today().date()
    if "last_date_lain" not in st.session_state:
        st.session_state.last_date_lain = today_date_lain

    with st.container(border=True):
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            tgl_lain = st.date_input("Tanggal Transaksi", st.session_state.last_date_lain, max_value=datetime.today(), format="DD/MM/YYYY", key=f"tgl_lain_{st.session_state.form_counter_lain}")
        with col_l2:
            jenis_transaksi = st.radio("Jenis Transaksi", ["Penambahan (+)", "Pengeluaran (-)"], horizontal=True, key=f"jenis_lain_{st.session_state.form_counter_lain}")
            
        ket_lain = st.text_input("Keterangan / Catatan (Contoh: Sisa Nota Tanggal Kemarin)", key=f"ket_lain_{st.session_state.form_counter_lain}")
        nominal_lain_str = st.text_input("Nominal (Rp)", value="", placeholder="Contoh: 50000", key=f"nom_lain_{st.session_state.form_counter_lain}")
        
        notif_area_lain = st.empty()
        if "notif_lain_msg" in st.session_state:
            if st.session_state.notif_type_lain == "success":
                notif_area_lain.success(st.session_state.notif_lain_msg)
            else:
                notif_area_lain.error(st.session_state.notif_lain_msg)
            
            del st.session_state.notif_lain_msg
            del st.session_state.notif_type_lain
            
            components.html(
                """<script>
                setTimeout(function() {
                    const alerts = window.parent.document.querySelectorAll('[data-testid="stAlert"]');
                    if (alerts && alerts.length > 0) {
                        alerts[alerts.length - 1].style.display = 'none';
                    }
                }, 2500);
                </script>""", height=0
            )

        btn_save_lain = st.button("💾 Simpan Transaksi Lain", type="primary", use_container_width=True)

    if btn_save_lain:
        st.session_state.last_date_lain = tgl_lain
        clean_lain = nominal_lain_str.strip() if nominal_lain_str else ""
        nom_val = int(clean_lain) if clean_lain.isdigit() else 0
        if nom_val > 0:
            id_l = f"LAIN-{int(time.time()*1000)}"
            tgl_str_l = tgl_lain.strftime("%Y-%m-%d")
            nama_hari_l = HARI_INDO[tgl_lain.strftime("%A")]
            baris_l = pd.DataFrame([{
                "ID Lain": id_l,
                "Hari": nama_hari_l,
                "Tanggal": tgl_str_l,
                "Jenis": jenis_transaksi,
                "Keterangan": ket_lain if ket_lain.strip() else "-",
                "Nominal": nom_val
            }])
            st.session_state.df_lain = pd.concat([st.session_state.df_lain, baris_l], ignore_index=True)
            
            background_sync(st.session_state.df_lain, "Data_Pengeluaran_Lain")
            
            nom_rp_str = f"Rp {nom_val:,.0f}".replace(",", ".")
            st.session_state.notif_lain_msg = f"✅ TERSIMPAN! Nominal: {nom_rp_str}"
            st.session_state.notif_type_lain = "success"
            
            st.session_state.form_counter_lain += 1
            st.rerun()
        else:
            st.session_state.notif_lain_msg = "⚠️ Mohon masukkan nominal angka yang valid."
            st.session_state.notif_type_lain = "error"
            st.rerun()

    components.html("""
    <script>
    const doc = window.parent.document;
    if (!doc.getElementById('custom-enter-save-script-lain')) {
        doc.body.insertAdjacentHTML('beforeend', '<div id="custom-enter-save-script-lain" style="display:none;"></div>');
        doc.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                const active = doc.activeElement;
                if (active && active.tagName === 'INPUT' && (active.type === 'text' || active.type === 'number')) {
                    const btns = Array.from(doc.querySelectorAll('button'));
                    const saveBtn = btns.find(b => b.innerText.includes('Simpan Transaksi Lain') && b.offsetParent !== null);
                    if (saveBtn) {
                        e.preventDefault();
                        e.stopPropagation();
                        saveBtn.focus();
                        setTimeout(() => { saveBtn.click(); }, 50);
                    }
                }
            }
        }, true);
    }
    </script>
    """, height=0, width=0)

    st.markdown("---")
    st.subheader("Database Pengeluaran & Penambahan Lain")
    
    df_lain = st.session_state.df_lain.copy()
    if len(df_lain) > 0:
        if 'Hari' not in df_lain.columns:
            df_lain['Hari'] = pd.to_datetime(df_lain['Tanggal']).dt.strftime('%A').map(HARI_INDO).fillna("Senin")
            st.session_state.df_lain = df_lain.copy()
        if 'Jenis' not in df_lain.columns:
            df_lain['Jenis'] = "Penambahan (+)"
            st.session_state.df_lain = df_lain.copy()

        df_lain['Date_Obj'] = pd.to_datetime(df_lain['Tanggal']).dt.date
        max_tgl_l = df_lain['Date_Obj'].max()
        min_tgl_l = df_lain['Date_Obj'].min()
        
        col_fl1, col_fl2 = st.columns([2, 1])
        with col_fl1:
            rentang_tgl_lain = st.date_input("Pilih Periode Tanggal", value=(min_tgl_l, max_tgl_l), max_value=datetime.today().date(), format="DD/MM/YYYY", key="periode_lain")
        with col_fl2:
            opsi_jenis_lain = ["Semua Transaksi", "Penambahan (+)", "Pengeluaran (-)"]
            filter_jenis_lain = st.selectbox("🔍 Filter Transaksi:", opsi_jenis_lain, key="filter_jenis_lain")
        
        if isinstance(rentang_tgl_lain, tuple) and len(rentang_tgl_lain) == 2:
            t_mulai_l, t_selesai_l = rentang_tgl_lain
        else:
            t_mulai_l = t_selesai_l = rentang_tgl_lain[0] if isinstance(rentang_tgl_lain, tuple) else rentang_tgl_lain

        df_lain_tampil = df_lain[(df_lain['Date_Obj'] >= t_mulai_l) & (df_lain['Date_Obj'] <= t_selesai_l)].copy()
        if filter_jenis_lain != "Semua Transaksi":
            df_lain_tampil = df_lain_tampil[df_lain_tampil['Jenis'] == filter_jenis_lain]
        
        if len(df_lain_tampil) > 0:
            df_lain_tampil['Urutan_Hari'] = df_lain_tampil['Hari'].map(URUTAN_HARI).fillna(8)
            df_lain_tampil = df_lain_tampil.sort_values(by=["Tanggal", "Urutan_Hari"], ascending=[False, True]).drop(columns=["Urutan_Hari", "Date_Obj"])
            
            daftar_tanggal_l = df_lain_tampil[['Tanggal', 'Hari']].drop_duplicates().values
            
            for tgl_l, hari_l in daftar_tanggal_l:
                tgl_format_l = datetime.strptime(str(tgl_l), "%Y-%m-%d").strftime("%d-%m-%Y")
                with st.expander(f"📅 Hari **{hari_l}**, **{tgl_format_l}**", expanded=True):
                    df_harian_l = df_lain_tampil[(df_lain_tampil['Tanggal'] == tgl_l) & (df_lain_tampil['Hari'] == hari_l)].copy()
                    
                    df_harian_l_view = df_harian_l[['ID Lain', 'Jenis', 'Keterangan', 'Nominal']].copy().reset_index(drop=True)
                    df_harian_l_view['Nominal'] = pd.to_numeric(df_harian_l_view['Nominal'], errors='coerce').fillna(0)
                    
                    tambah_harian = df_harian_l_view[df_harian_l_view['Jenis'] == 'Penambahan (+)']['Nominal'].sum()
                    kurang_harian = df_harian_l_view[df_harian_l_view['Jenis'] == 'Pengeluaran (-)']['Nominal'].sum()
                    neto_harian = tambah_harian - kurang_harian
                    
                    edited_lain = st.data_editor(
                        df_harian_l_view,
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "ID Lain": None,
                            "Nominal": st.column_config.NumberColumn(format="Rp %,d")
                        },
                        key=f"editor_lain_{tgl_l}_{hari_l}"
                    )
                    
                    st.markdown(f"🔹 **Neto Hari Ini ({tgl_format_l}):** `Rp {neto_harian:,.0f}` *(+Rp {tambah_harian:,.0f} | -Rp {kurang_harian:,.0f})*".replace(",", "."))
                    
                    orig_ids_l = set(df_harian_l_view['ID Lain'].dropna().tolist())
                    curr_ids_l = set(edited_lain['ID Lain'].dropna().tolist() if 'ID Lain' in edited_lain.columns else [])
                    deleted_ids_l = list(orig_ids_l - curr_ids_l)
                    
                    if deleted_ids_l or len(edited_lain) < len(df_harian_l_view):
                        st.session_state.df_lain = st.session_state.df_lain[~st.session_state.df_lain['ID Lain'].isin(deleted_ids_l)].copy()
                        background_sync(st.session_state.df_lain, "Data_Pengeluaran_Lain")
                        st.success("✅ Data berhasil dihapus!")
                        st.rerun()
        else:
            st.info("Tidak ada data transaksi lain pada rentang tanggal atau filter tersebut.")
    else:
        st.info("Belum ada data transaksi lain yang tercatat.")

# ==========================================
# MENU 4: CETAK INVOICE
# ==========================================
with menu4:
    st.header("Cetak Invoice Transaksi")
    st.caption("💡 Invoice otomatis memisahkan rincian produksi, penambahan, dan pengeluaran secara transparan dan sangat mudah dibaca.")

    df_nota_inv = st.session_state.df_nota.copy()
    df_lain_inv = st.session_state.df_lain.copy()

    if len(df_nota_inv) > 0 or len(df_lain_inv) > 0:
        all_dates = []
        if len(df_nota_inv) > 0:
            df_nota_inv['Date_Obj'] = pd.to_datetime(df_nota_inv['Tanggal']).dt.date
            all_dates.extend(df_nota_inv['Date_Obj'].tolist())
        if len(df_lain_inv) > 0:
            df_lain_inv['Date_Obj'] = pd.to_datetime(df_lain_inv['Tanggal']).dt.date
            all_dates.extend(df_lain_inv['Date_Obj'].tolist())

        min_inv = min(all_dates) if all_dates else datetime.today().date()
        max_inv = max(all_dates) if all_dates else datetime.today().date()
        
        rentang_inv = st.date_input("Pilih Periode Invoice", value=(min_inv, max_inv), max_value=datetime.today().date(), format="DD/MM/YYYY", key="periode_invoice")
        
        if isinstance(rentang_inv, tuple) and len(rentang_inv) == 2:
            t_start_inv, t_end_inv = rentang_inv
        else:
            t_start_inv = t_end_inv = rentang_inv[0] if isinstance(rentang_inv, tuple) else rentang_inv

        df_f_inv = df_nota_inv[(df_nota_inv['Date_Obj'] >= t_start_inv) & (df_nota_inv['Date_Obj'] <= t_end_inv)].copy() if len(df_nota_inv) > 0 else pd.DataFrame()
        
        df_f_lain_inv = pd.DataFrame()
        if len(df_lain_inv) > 0:
            df_f_lain_inv = df_lain_inv[(df_lain_inv['Date_Obj'] >= t_start_inv) & (df_lain_inv['Date_Obj'] <= t_end_inv)].copy()

        if st.button("🖼️ Generate Invoice JPG Profesional", type="primary"):
            if len(df_f_inv) > 0 or len(df_f_lain_inv) > 0:
                scale = 2
                
                try:
                    f_title = ImageFont.truetype("Roboto-Bold.ttf", 22 * scale)
                    f_section = ImageFont.truetype("Roboto-Bold.ttf", 13 * scale)
                    f_header = ImageFont.truetype("Roboto-Bold.ttf", 12 * scale)
                    f_bold = ImageFont.truetype("Roboto-Bold.ttf", 12 * scale)
                    f_text = ImageFont.truetype("Roboto-Regular.ttf", 12 * scale)
                except:
                    f_title = ImageFont.load_default()
                    f_section = ImageFont.load_default()
                    f_header = ImageFont.load_default()
                    f_bold = ImageFont.load_default()
                    f_text = ImageFont.load_default()

                img_w = 880 * scale
                margin = 40 * scale
                row_h = 35 * scale
                
                df_tambah = df_f_lain_inv[df_f_lain_inv['Jenis'].str.contains("Penambahan", na=False)] if len(df_f_lain_inv) > 0 else pd.DataFrame()
                df_kurang = df_f_lain_inv[df_f_lain_inv['Jenis'].str.contains("Pengeluaran", na=False)] if len(df_f_lain_inv) > 0 else pd.DataFrame()

                num_nota_rows = len(df_f_inv)
                num_tambah_rows = len(df_tambah)
                num_kurang_rows = len(df_kurang)
                
                header_h = 140 * scale
                table_header_h = 35 * scale
                subtotal_row_h = 35 * scale
                section_title_h = 30 * scale
                footer_h = 140 * scale
                
                extra_h = 0
                if num_nota_rows > 0:
                    extra_h += section_title_h + table_header_h + (num_nota_rows * row_h) + subtotal_row_h + 20 * scale
                if num_tambah_rows > 0:
                    extra_h += section_title_h + table_header_h + (num_tambah_rows * row_h) + subtotal_row_h + 20 * scale
                if num_kurang_rows > 0:
                    extra_h += section_title_h + table_header_h + (num_kurang_rows * row_h) + subtotal_row_h + 20 * scale
                
                img_h = header_h + extra_h + footer_h

                img_inv = Image.new('RGB', (img_w, img_h), color=(255, 255, 255))
                draw = ImageDraw.Draw(img_inv)

                # --- 1. HEADER INVOICE ---
                draw.text((margin, 35 * scale), "INVOICE PRODUKSI STYROFOAM", fill=(0, 0, 0), font=f_title)
                draw.text((margin, 70 * scale), f"Periode Tanggal: {t_start_inv.strftime('%d/%m/%Y')} s/d {t_end_inv.strftime('%d/%m/%Y')}", fill=(80, 80, 80), font=f_bold)
                draw.line([(margin, 100 * scale), (img_w - margin, 100 * scale)], fill=(0, 0, 0), width=2 * scale)

                y_tbl = 120 * scale
                grand_total = 0
                box_size = 14 * scale
                box_x_pos = img_w - margin - 30 * scale 

                # --- 2. BAGIAN PRODUKSI ---
                subtotal_nota = 0
                if num_nota_rows > 0:
                    draw.text((margin, y_tbl), "Rincian Pekerjaan Produksi", fill=(30, 30, 30), font=f_section)
                    y_tbl += section_title_h

                    draw.rectangle([margin, y_tbl, img_w - margin, y_tbl + table_header_h], fill=(240, 240, 240))
                    col_x = [margin + 10, margin + 120 * scale, margin + 430 * scale, margin + 550 * scale, margin + 660 * scale]
                    draw.text((col_x[0], y_tbl + 8 * scale), "Tanggal", fill=(0, 0, 0), font=f_header)
                    draw.text((col_x[1], y_tbl + 8 * scale), "Jenis Pekerjaan & Status", fill=(0, 0, 0), font=f_header)
                    draw.text((col_x[2], y_tbl + 8 * scale), "Harga", fill=(0, 0, 0), font=f_header)
                    draw.text((col_x[3], y_tbl + 8 * scale), "Qty (Pcs)", fill=(0, 0, 0), font=f_header)
                    draw.text((col_x[4], y_tbl + 8 * scale), "Subtotal", fill=(0, 0, 0), font=f_header)
                    draw.text((box_x_pos, y_tbl + 8 * scale), "[ ]", fill=(0, 0, 0), font=f_header)
                    y_tbl += table_header_h

                    for _, row in df_f_inv.iterrows():
                        tgl_row = str(row['Tanggal'])
                        try:
                            tgl_format_row = datetime.strptime(tgl_row, "%Y-%m-%d").strftime("%d/%m/%Y")
                        except:
                            tgl_format_row = tgl_row

                        j_pek = str(row['Jenis Pekerjaan'])
                        status_p = str(row['Status Pengiriman'])
                        pot_o = float(row['Potongan Ongkir']) if 'Potongan Ongkir' in row and pd.notna(row['Potongan Ongkir']) else 0
                        tam_o = float(row['Tambahan Ongkir']) if 'Tambahan Ongkir' in row and pd.notna(row['Tambahan Ongkir']) else 0

                        if status_p == "Diambil" and pot_o > 0:
                            j_pek_label = f"{j_pek} (Diambil - Pot. Rp {pot_o:,.0f})".replace(",", ".")
                        elif status_p == "Subsidi Ongkir" and tam_o > 0:
                            j_pek_label = f"{j_pek} (Subsidi Ongkir + Rp {tam_o:,.0f})".replace(",", ".")
                        else:
                            j_pek_label = f"{j_pek} ({status_p})"

                        harga = float(row['Harga Satuan'])
                        qty = float(row['Jumlah (pcs)'])
                        sub = float(row['Total Bersih'])
                        subtotal_nota += sub

                        draw.line([(margin, y_tbl + row_h), (img_w - margin, y_tbl + row_h)], fill=(220, 220, 220), width=1)
                        
                        box_y = y_tbl + (row_h - box_size) // 2
                        draw.rectangle([box_x_pos, box_y, box_x_pos + box_size, box_y + box_size], outline=(0, 0, 0), width=2 * scale, fill=(255, 255, 255))

                        draw.text((col_x[0], y_tbl + 8 * scale), tgl_format_row, fill=(0, 0, 0), font=f_text)
                        draw.text((col_x[1], y_tbl + 8 * scale), j_pek_label, fill=(0, 0, 0), font=f_text)
                        draw.text((col_x[2], y_tbl + 8 * scale), f"Rp {harga:,.0f}".replace(",", "."), fill=(0, 0, 0), font=f_text)
                        draw.text((col_x[3], y_tbl + 8 * scale), f"{qty:,.0f}".replace(",", "."), fill=(0, 0, 0), font=f_text)
                        draw.text((col_x[4], y_tbl + 8 * scale), f"Rp {sub:,.0f}".replace(",", "."), fill=(0, 0, 0), font=f_text)
                        y_tbl += row_h

                    grand_total += subtotal_nota
                    draw.rectangle([margin, y_tbl, img_w - margin, y_tbl + subtotal_row_h], fill=(245, 245, 245))
                    draw.text((margin + 10, y_tbl + 8 * scale), "Subtotal Produksi:", fill=(0, 0, 0), font=f_bold)
                    sub_nota_str = f"Rp {subtotal_nota:,.0f}".replace(",", ".")
                    bbox_sn = draw.textbbox((0, 0), sub_nota_str, font=f_bold)
                    draw.text((box_x_pos - 20 * scale - (bbox_sn[2] - bbox_sn[0]), y_tbl + 8 * scale), sub_nota_str, fill=(0, 0, 0), font=f_bold)
                    y_tbl += subtotal_row_h + 20 * scale

                # --- 3. BAGIAN PENAMBAHAN LAIN ---
                subtotal_tambah = 0
                if num_tambah_rows > 0:
                    draw.text((margin, y_tbl), "Penambahan Lain (Sisa Nota / Penyesuaian +)", fill=(0, 100, 0), font=f_section)
                    y_tbl += section_title_h

                    draw.rectangle([margin, y_tbl, img_w - margin, y_tbl + table_header_h], fill=(240, 240, 240))
                    col_lx = [margin + 10, margin + 130 * scale, margin + 480 * scale]
                    draw.text((col_lx[0], y_tbl + 8 * scale), "Tanggal", fill=(0, 0, 0), font=f_header)
                    draw.text((col_lx[1], y_tbl + 8 * scale), "Keterangan", fill=(0, 0, 0), font=f_header)
                    draw.text((col_lx[2], y_tbl + 8 * scale), "Nominal Penambahan", fill=(0, 0, 0), font=f_header)
                    draw.text((box_x_pos, y_tbl + 8 * scale), "[ ]", fill=(0, 0, 0), font=f_header)
                    y_tbl += table_header_h

                    for _, row in df_tambah.iterrows():
                        tgl_row = str(row['Tanggal'])
                        try:
                            tgl_format_row = datetime.strptime(tgl_row, "%Y-%m-%d").strftime("%d/%m/%Y")
                        except:
                            tgl_format_row = tgl_row

                        ket = str(row['Keterangan'])
                        nom = float(row['Nominal'])
                        subtotal_tambah += nom

                        draw.line([(margin, y_tbl + row_h), (img_w - margin, y_tbl + row_h)], fill=(220, 220, 220), width=1)
                        
                        box_y = y_tbl + (row_h - box_size) // 2
                        draw.rectangle([box_x_pos, box_y, box_x_pos + box_size, box_y + box_size], outline=(0, 0, 0), width=2 * scale, fill=(255, 255, 255))

                        draw.text((col_lx[0], y_tbl + 8 * scale), tgl_format_row, fill=(0, 0, 0), font=f_text)
                        draw.text((col_lx[1], y_tbl + 8 * scale), ket, fill=(0, 0, 0), font=f_text)
                        nom_str = f"+ Rp {nom:,.0f}".replace(",", ".")
                        bbox_n = draw.textbbox((0, 0), nom_str, font=f_text)
                        draw.text((box_x_pos - 20 * scale - (bbox_n[2] - bbox_n[0]), y_tbl + 8 * scale), nom_str, fill=(0, 120, 0), font=f_text)
                        y_tbl += row_h

                    grand_total += subtotal_tambah
                    draw.rectangle([margin, y_tbl, img_w - margin, y_tbl + subtotal_row_h], fill=(245, 245, 245))
                    draw.text((margin + 10, y_tbl + 8 * scale), "Subtotal Penambahan Lain:", fill=(0, 0, 0), font=f_bold)
                    sub_tambah_str = f"+ Rp {subtotal_tambah:,.0f}".replace(",", ".")
                    bbox_st = draw.textbbox((0, 0), sub_tambah_str, font=f_bold)
                    draw.text((box_x_pos - 20 * scale - (bbox_st[2] - bbox_st[0]), y_tbl + 8 * scale), sub_tambah_str, fill=(0, 120, 0), font=f_bold)
                    y_tbl += subtotal_row_h + 20 * scale

                # --- 4. BAGIAN PENGELUARAN LAIN ---
                subtotal_kurang = 0
                if num_kurang_rows > 0:
                    draw.text((margin, y_tbl), "Pengeluaran / Potongan Lain (-)", fill=(180, 0, 0), font=f_section)
                    y_tbl += section_title_h

                    draw.rectangle([margin, y_tbl, img_w - margin, y_tbl + table_header_h], fill=(240, 240, 240))
                    col_lx = [margin + 10, margin + 130 * scale, margin + 480 * scale]
                    draw.text((col_lx[0], y_tbl + 8 * scale), "Tanggal", fill=(0, 0, 0), font=f_header)
                    draw.text((col_lx[1], y_tbl + 8 * scale), "Keterangan", fill=(0, 0, 0), font=f_header)
                    draw.text((col_lx[2], y_tbl + 8 * scale), "Nominal Pengeluaran", fill=(0, 0, 0), font=f_header)
                    draw.text((box_x_pos, y_tbl + 8 * scale), "[ ]", fill=(0, 0, 0), font=f_header)
                    y_tbl += table_header_h

                    for _, row in df_kurang.iterrows():
                        tgl_row = str(row['Tanggal'])
                        try:
                            tgl_format_row = datetime.strptime(tgl_row, "%Y-%m-%d").strftime("%d/%m/%Y")
                        except:
                            tgl_format_row = tgl_row

                        ket = str(row['Keterangan'])
                        nom = float(row['Nominal'])
                        subtotal_kurang += nom

                        draw.line([(margin, y_tbl + row_h), (img_w - margin, y_tbl + row_h)], fill=(220, 220, 220), width=1)
                        
                        box_y = y_tbl + (row_h - box_size) // 2
                        draw.rectangle([box_x_pos, box_y, box_x_pos + box_size, box_y + box_size], outline=(0, 0, 0), width=2 * scale, fill=(255, 255, 255))

                        draw.text((col_lx[0], y_tbl + 8 * scale), tgl_format_row, fill=(0, 0, 0), font=f_text)
                        draw.text((col_lx[1], y_tbl + 8 * scale), ket, fill=(0, 0, 0), font=f_text)
                        nom_str = f"- Rp {nom:,.0f}".replace(",", ".")
                        bbox_n = draw.textbbox((0, 0), nom_str, font=f_text)
                        draw.text((box_x_pos - 20 * scale - (bbox_n[2] - bbox_n[0]), y_tbl + 8 * scale), nom_str, fill=(180, 0, 0), font=f_text)
                        y_tbl += row_h

                    grand_total -= subtotal_kurang
                    draw.rectangle([margin, y_tbl, img_w - margin, y_tbl + subtotal_row_h], fill=(245, 245, 245))
                    draw.text((margin + 10, y_tbl + 8 * scale), "Subtotal Pengeluaran Lain:", fill=(0, 0, 0), font=f_bold)
                    sub_kurang_str = f"- Rp {subtotal_kurang:,.0f}".replace(",", ".")
                    bbox_sk = draw.textbbox((0, 0), sub_kurang_str, font=f_bold)
                    draw.text((box_x_pos - 20 * scale - (bbox_sk[2] - bbox_sk[0]), y_tbl + 8 * scale), sub_kurang_str, fill=(180, 0, 0), font=f_bold)
                    y_tbl += subtotal_row_h + 20 * scale

                # --- 5. TOTAL KESELURUHAN AKHIR ---
                y_tbl += 10 * scale
                draw.line([(margin, y_tbl), (img_w - margin, y_tbl)], fill=(0, 0, 0), width=2 * scale)
                y_tbl += 20 * scale

                draw.text((margin, y_tbl), "TOTAL KESELURUHAN BERSIH:", fill=(0, 0, 0), font=f_title)
                total_str = f"Rp {grand_total:,.0f}".replace(",", ".")
                
                bbox = draw.textbbox((0, 0), total_str, font=f_title)
                t_width = bbox[2] - bbox[0]
                draw.text((img_w - margin - t_width, y_tbl), total_str, fill=(0, 100, 0), font=f_title)

                buf_inv = io.BytesIO()
                img_inv.save(buf_inv, format="JPEG", quality=100)
                byte_inv = buf_inv.getvalue()

                st.markdown("---")
                st.subheader("👁️ Preview Invoice Profesional")
                st.image(byte_inv, width=600)

                b64_inv = base64.b64encode(byte_inv).decode()
                print_html = f"""
                <div style="margin-bottom: 10px;">
                    <button onclick="printInvoice()" style="background-color: #2e7d32; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px;">🖨️ PRINT INVOICE LANGSUNG</button>
                </div>
                <script>
                function printInvoice() {{
                    var win = window.open('', '_blank');
                    win.document.write('<html><head><title>Print Invoice</title>');
                    win.document.write('<style>body {{ text-align: center; margin: 0; background: white; }} img {{ width: 100%; max-width: 880px; }}</style>');
                    win.document.write('</head><body><img src="data:image/jpeg;base64,{b64_inv}" onload="window.print(); window.close();" /></body></html>');
                    win.document.close();
                }}
                </script>
                """
                components.html(print_html, height=70)
                st.download_button("📥 Unduh Invoice (JPG)", data=byte_inv, file_name=f"Invoice_{t_start_inv.strftime('%d%m%Y')}.jpg", mime="image/jpeg")
            else:
                st.warning("Tidak ada data transaksi pada rentang tanggal tersebut.")
    else:
        st.info("Belum ada data transaksi untuk dibuatkan invoice.")

# ==========================================
# MENU 5: PENGATURAN
# ==========================================
with menu5:
    st.header("Pengaturan Master Pekerjaan")
    st.caption("💡 Atur daftar Jenis Pekerjaan dan Harga Satuan (per pcs) di bawah ini. Klik **Simpan** untuk memperbarui.")
    
    df_pek_view = st.session_state['pengaturan_pekerjaan'].copy().reset_index(drop=True)
    df_pek_view['Harga Satuan (Rp)'] = pd.to_numeric(df_pek_view['Harga Satuan (Rp)'], errors='coerce').fillna(0)
    
    notif_area_setting = st.empty()
    if "setting_msg" in st.session_state:
        if st.session_state.setting_type == "success":
            notif_area_setting.success(st.session_state.setting_msg)
        else:
            notif_area_setting.error(st.session_state.setting_msg)
        time.sleep(1.5)
        notif_area_setting.empty()
        del st.session_state.setting_msg
        del st.session_state.setting_type

    edited_pek = st.data_editor(
        df_pek_view,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Harga Satuan (Rp)": st.column_config.NumberColumn("Harga Satuan (Rp)", format="Rp %,d")
        },
        key="editor_master_pekerjaan"
    )
    
    if st.button("💾 Simpan Pengaturan", type="primary"):
        cleaned_pek = edited_pek[edited_pek['Jenis Pekerjaan'].astype(str).str.strip() != ""].copy()
        cleaned_pek['Harga Satuan (Rp)'] = pd.to_numeric(cleaned_pek['Harga Satuan (Rp)'], errors='coerce').fillna(0)
        
        if not cleaned_pek.empty:
            st.session_state['pengaturan_pekerjaan'] = cleaned_pek
            st.session_state.setting_msg = "✅ Pengaturan Master Pekerjaan berhasil diperbarui!"
            st.session_state.setting_type = "success"
            st.rerun()
        else:
            st.session_state.setting_msg = "⚠️ Gagal! Master pekerjaan tidak boleh kosong."
            st.session_state.setting_type = "error"
            st.rerun()
