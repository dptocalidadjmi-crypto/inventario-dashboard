# Dashboard de Inventario (Streamlit Cloud)

Dashboard de inventario que lee directamente del export CSV de un Google Sheet.
Pensado para desplegarse gratis en [Streamlit Community Cloud](https://share.streamlit.io)
y embeberse en ClickUp.

## Despliegue

1. Sube esta carpeta como repositorio a GitHub (puede ser privado).
2. Entra a https://share.streamlit.io e inicia sesión con GitHub.
3. "Create app" → elige este repo → archivo principal: `streamlit_app.py`.
4. En **App settings → Secrets** pega:

   ```toml
   SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/<ID-DEL-SHEET>/export?format=csv"
   LOW_STOCK_DEFAULT_THRESHOLD = "5"
   ```

5. El Google Sheet debe estar compartido como **"Cualquiera con el enlace puede ver"**,
   si no, Google devuelve una página de login en lugar del CSV.

## Embeber en ClickUp

1. En ClickUp: vista **+ View → Embed**.
2. Pega la URL de la app agregando `?embed=true` al final:

   ```
   https://<tu-app>.streamlit.app/?embed=true
   ```

## Nota de privacidad

La app desplegada es pública (cualquiera con la URL puede verla). No contiene
credenciales: la URL del Sheet vive en los Secrets de Streamlit Cloud, no en el código.

## Prueba local

```bash
python -m pip install -r requirements.txt
set SHEET_CSV_URL=https://docs.google.com/spreadsheets/d/<ID>/export?format=csv
python -m streamlit run streamlit_app.py
```
