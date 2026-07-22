import streamlit as st
import theme

theme.inject()
theme.hero()

st.markdown(
    '<p class="cy-subtitle">Traccia il bilanciere e calcola velocità, potenza e stima '
    'dell\'1RM del giorno con l\'algoritmo VBT — interfaccia da terminale di allenamento.</p>',
    unsafe_allow_html=True,
)

st.markdown('<span class="status-badge">● SYS.ONLINE</span>', unsafe_allow_html=True)
st.write("")

theme.step_header("Moduli disponibili", index="//")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        '<div class="cy-card">'
        '<div class="cy-card-title">🎯 Upload &amp; Tracking</div>'
        '<div class="cy-card-desc">Carica il video, scegli il punto sul bilanciere e avvia '
        'il tracciamento CSRT. Qui si configura anche la modalità VBT.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("Vai a Upload & Tracking →", use_container_width=True, type="primary"):
        st.switch_page("pages/2_upload_tracking.py")

with col2:
    st.markdown(
        '<div class="cy-card">'
        '<div class="cy-card-title">📊 Risultati</div>'
        '<div class="cy-card-desc">Video elaborato, dashboard VBT (velocità, potenza, '
        'ripetizioni), stima 1RM e feedback sulla fatica.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("Vai a Risultati →", use_container_width=True):
        st.switch_page("pages/3_risultati.py")

col3, col4 = st.columns(2)

with col3:
    st.markdown(
        '<div class="cy-card">'
        '<div class="cy-card-title">🗂️ Storico</div>'
        '<div class="cy-card-desc">Le serie elaborate in questa sessione: rivedi metriche '
        'e video già processati senza ripetere l\'analisi.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("Vai a Storico →", use_container_width=True):
        st.switch_page("pages/4_storico.py")

with col4:
    st.markdown(
        '<div class="cy-card">'
        '<div class="cy-card-title">⚙️ Come funziona</div>'
        '<div class="cy-card-desc">Guida rapida alle due modalità e ai parametri VBT.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Apri la guida", expanded=False):
        st.markdown(
            """
            1. Vai su **Upload & Tracking** e scegli la modalità (Solo Bar Path o VBT Avanzato).
            2. **Se sei in modalità VBT**, indica esercizio, peso sul bilanciere
               e diametro del disco: servono per calcolare velocità, potenza e
               1RM stimato.
            3. **Carica** un video (bilanciere già visibile nel primo fotogramma).
            4. **Clicca** su un punto ad alto contrasto del bilanciere (bordo di
               un disco, adesivo, anello) e regola l'area da seguire — in
               modalità VBT quest'area viene usata anche per calibrare la
               conversione pixel → metri, quindi conviene farla combaciare con
               l'altezza del disco.
            5. Premi **Analizza set**. Il tracciamento (CSRT) segue il punto in
               ogni fotogramma; passa poi su **Risultati** per la dashboard VBT
               completa (velocità, potenza, ripetizioni, 1RM stimato e feedback
               sulla fatica).

            💡 **Per una stima 1RM precisa**: la stima basata sulla velocità è
            pensata per serie brevi (1-3 ripetizioni) eseguite alla massima
            velocità possibile con un carico impegnativo — è così che funzionano
            tutti i dispositivi VBT commerciali. Su serie più lunghe o
            sub-massimali, l'app affianca automaticamente una stima classica
            basata sul numero di ripetizioni, più affidabile in quel caso.

            *Le stime VBT si basano su un tracciamento video 2D con una
            telecamera non calibrata: sono utili per il trend e per un feedback
            di massima, non sostituiscono un encoder lineare o un dispositivo VBT
            certificato.*
            """
        )

theme.footer()
