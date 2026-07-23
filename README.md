# PRAGMA FIT

Web app per il tracciamento del bilanciere durante gli allenamenti di forza, con analisi delle performance in tempo reale.

## Requisiti

- Python 3.10+
- Le dipendenze elencate in `requirements.txt`

## Installazione

```bash
pip install -r requirements.txt
```

## Avvio dell'applicazione

```bash
streamlit run app.py
```

L'app si apre nel browser all'indirizzo indicato dal terminale (di norma `http://localhost:8501`).

## Come si usa

1. **Home** — panoramica e accesso rapido alle sezioni.
2. **Upload & Tracking**
   - Scegli la modalità: *Solo Bar Path* oppure *VBT Avanzato*.
   - Se selezioni la modalità VBT, inserisci esercizio, peso sul bilanciere e diametro del disco.
   - Carica un video in cui il bilanciere sia visibile fin dal primo fotogramma.
   - Clicca sul bilanciere nell'anteprima per indicare il punto da seguire, regolando se serve la dimensione dell'area di tracciamento.
   - Premi **Analizza set** per avviare l'elaborazione.
3. **Risultati** — video con la traiettoria disegnata e, in modalità VBT, la dashboard con le metriche calcolate.
4. **Storico** — elenco delle serie elaborate nella sessione corrente, richiamabili in qualsiasi momento.

## Struttura del progetto

```
app.py                     punto di ingresso e navigazione tra le pagine
engine.py                  motore di elaborazione video e calcolo metriche
theme.py                   aspetto grafico dell'interfaccia
pages/                     le singole pagine dell'applicazione
assets/                    logo e risorse grafiche
requirements.txt           dipendenze del progetto
```

## Note

Le metriche mostrate sono stime calcolate da un video 2D non calibrato: vanno intese come indicazione di tendenza, non come dato clinico o strumentale certificato.
