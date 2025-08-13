from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from src.infrastructure.exporters.excel import export_excel
from src.services.process import process_pdf_bytes


router = APIRouter()

INDEX_HTML = """
<!DOCTYPE html>
<html lang="cs">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Valuagent – Finanční OCR</title>
    <link rel="icon" type="image/png" href="/static/logo.png" />
    <style>
      :root {
        --bg: #0b1020;
        --card: #ffffff;
        --text: #0b1020;
        --muted: #5b6479;
        --primary: #2b6ef6;
        --primary-600: #1f57c7;
        --ring: rgba(43, 110, 246, 0.3);
      }
      * { box-sizing: border-box; }
      html, body { height: 100%; }
      body {
        margin: 0; padding: 32px; color: var(--text);
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, Noto Sans, "Apple Color Emoji", "Segoe UI Emoji";
        background: radial-gradient(1200px 600px at 20% -10%, #233161, transparent 60%),
                    radial-gradient(1000px 600px at 100% 0%, #1f2a52, transparent 50%),
                    var(--bg);
      }
      .container {
        max-width: 980px; margin: 0 auto;
        display: grid; gap: 24px;
      }
      .hero {
        display: flex; align-items: center; gap: 16px;
        color: #e9eefc;
      }
      .hero img { height: 56px; width: 56px; border-radius: 10px; background: #fff; padding: 6px; }
      .hero h1 { font-size: 28px; line-height: 1.2; margin: 0; font-weight: 700; }
      .hero p { margin: 2px 0 0 0; color: #b7c2e7; }

      .card {
        background: var(--card); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(16, 24, 40, .18);
        display: grid; grid-template-columns: 1.2fr .8fr; gap: 24px;
      }
      @media (max-width: 920px) {
        .card { grid-template-columns: 1fr; }
      }
      .section-title { font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 0 0 8px; }

      form { display: grid; gap: 14px; }
      label { font-size: 14px; color: var(--muted); display: grid; gap: 6px; }
      input[type="number"], select {
        border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px 12px; font-size: 16px;
        outline: none; background: #fff; color: var(--text);
      }
      input[type="number"]:focus, select:focus { border-color: var(--primary); box-shadow: 0 0 0 4px var(--ring); }

      .dropzone {
        border: 2px dashed #cdd5e1; border-radius: 12px; padding: 18px; background: #f8fafc; transition: .15s ease;
        display: grid; gap: 8px; justify-items: center; text-align: center; cursor: pointer;
      }
      .dropzone:hover { background: #f1f5f9; }
      .dropzone.is-dragover { border-color: var(--primary); background: #eef4ff; box-shadow: inset 0 0 0 3px var(--ring); }
      .dropzone strong { color: var(--text); }
      .hint { font-size: 12px; color: #64748b; }
      /* Settings panel */
      details.settings { border: 1px solid #e5e7eb; border-radius: 12px; padding: 10px 12px; background: #f8fafc; }
      details.settings[open] { background: #eef4ff; }
      details.settings summary { cursor: pointer; font-weight: 600; color: var(--text); list-style: none; }
      details.settings summary::-webkit-details-marker { display: none; }
      .settings-body { margin-top: 8px; display: grid; gap: 10px; }
      .notice { margin-top: 6px; font-size: 14px; display: none; }
      .notice--error { color: #b91c1c; display: block; }
      .notice--success { color: #166534; display: block; }

      .actions { display: flex; align-items: center; gap: 12px; margin-top: 4px; }
      button[type="submit"] {
        background: var(--primary); color: #fff; border: 0; border-radius: 10px; padding: 10px 16px; font-size: 16px; font-weight: 600; cursor: pointer;
        box-shadow: 0 8px 20px rgba(43, 110, 246, .35);
      }
      button[type="submit"]:hover { background: var(--primary-600); }
      button[disabled] { opacity: .7; cursor: not-allowed; box-shadow: none; }

      /* Segmented switch */
      .segmented { display: grid; grid-template-columns: 1fr 1fr; width: 100%; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; background: #fff; }
      .segmented button { appearance: none; background: #fff; color: var(--muted); border: 0; padding: 10px 12px; font-weight: 600; cursor: pointer; font-size: 15px; min-height: 44px; }
      .segmented button + button { border-left: 1px solid #e5e7eb; margin-left: 0; }
      .segmented button.is-active { background: var(--primary); color: #fff; }
      .segmented button:focus-visible { outline: none; box-shadow: inset 0 0 0 2px #fff, 0 0 0 4px var(--ring); position: relative; z-index: 1; }

      .aside { border-left: 1px solid #eef2f7; padding-left: 24px; }
      @media (max-width: 920px) { .aside { border: 0; padding: 0; } }
      .list { margin: 0; padding-left: 18px; color: #222; }
      .list li { margin: 6px 0; color: #334155; }

      .footer { color: #a9b4d0; font-size: 12px; text-align: center; margin-top: 8px; }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="hero">
        <img src="/static/logo.png" alt="Valuagent logo" onerror="this.style.display='none'"/>
        <div>
          <h1>Valuagent</h1>
          <p>OCR s umělou inteligencí pro české účetní výkazy</p>
        </div>
      </div>

      <div class="card">
        <div>
          <p class="section-title">Nahrát</p>
          <form id="upload-form" action="/process" method="post" enctype="multipart/form-data" autocomplete="off">
            <label>
              Soubor (PDF)
              <input id="file-input" type="file" name="pdf" accept="application/pdf" required style="display:none" />
              <div id="dropzone" class="dropzone">
                <strong>Přetáhněte sem PDF</strong>
                <div class="hint">nebo klikněte pro výběr</div>
                <div id="file-name" class="hint"></div>
              </div>
            </label>

            <label>
              Výkaz
              <input type="hidden" name="statement_type" id="statement_type" value="rozvaha" />
              <div class="segmented" role="group" aria-label="Typ výkazu">
                <button type="button" class="is-active" data-value="rozvaha">Rozvaha</button>
                <button type="button" data-value="vzz">VZZ</button>
              </div>
            </label>

            <details class="settings">
              <summary>Nastavení</summary>
              <div class="settings-body">
                <label>
                  Tolerance
                  <input type="number" name="tolerance" value="1" min="0" placeholder="0 = přísné porovnání" />
                  <div class="hint">Většina českých výkazů je uváděna v tis. Kč. Kvůli zaokrouhlování mohou kontrolní součty někdy nesedět (typicky o 1). Tolerance umožní tyto drobné odchylky akceptovat.</div>
                </label>
              </div>
            </details>

            <div class="actions">
              <button id="submit-btn" type="submit">Zpracovat a stáhnout Excel</button>
              <span class="hint">Po úspěšném zpracování se stáhne soubor .xlsx.</span>
            </div>
            <div id="notice" class="notice" aria-live="polite"></div>
          </form>
        </div>
        <aside class="aside">
          <p class="section-title">Jak to funguje</p>
          <ol class="list">
            <li>Nahrajte PDF českého účetního výkazu.</li>
            <li>Vyberte typ výkazu a případně toleranci.</li>
            <li>Data vytěžíme, zkontrolujeme a předáme čistý Excel.</li>
          </ol>
          <p class="section-title" style="margin-top:16px">Proč Valuagent</p>
          <ul class="list">
            <li>Optimalizováno pro Rozvahu a Výkaz zisku a ztráty.</li>
            <li>Kontrolní pravidla zvýrazní nesrovnalosti.</li>
            <li>Připravený export pro analýzu a reportování.</li>
          </ul>
        </aside>
      </div>

      <div class="footer">Vaše soubory neukládáme. Zpracování je dočasné.</div>
    </div>

    <script>
      (function(){
        const drop = document.getElementById('dropzone');
        const input = document.getElementById('file-input');
        const fileName = document.getElementById('file-name');
        const form = document.getElementById('upload-form');
        const submitBtn = document.getElementById('submit-btn');
        const notice = document.getElementById('notice');

        const showName = (file) => { fileName.textContent = file ? file.name : ''; };
        const typeHidden = document.getElementById('statement_type');
        const typeButtons = Array.from(document.querySelectorAll('.segmented button'));
        typeButtons.forEach(btn => btn.addEventListener('click', () => {
          typeButtons.forEach(b => b.classList.remove('is-active'));
          btn.classList.add('is-active');
          typeHidden.value = btn.dataset.value;
        }));
        const setNotice = (message, type) => {
          notice.textContent = message || '';
          notice.className = 'notice' + (type ? ` notice--${type}` : '');
        };

        drop.addEventListener('click', () => input.click());
        drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('is-dragover'); });
        drop.addEventListener('dragleave', () => drop.classList.remove('is-dragover'));
        drop.addEventListener('drop', (e) => {
          e.preventDefault();
          drop.classList.remove('is-dragover');
          if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const file = e.dataTransfer.files[0];
            if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
              input.files = e.dataTransfer.files;
              showName(file);
            } else {
              alert('Nahrajte prosím soubor PDF.');
            }
          }
        });
        input.addEventListener('change', () => showName(input.files[0]));

        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          setNotice('', '');
          submitBtn.disabled = true;
          const previousText = submitBtn.textContent;
          submitBtn.textContent = 'Zpracovávám…';
          try {
            const formData = new FormData(form);
            const response = await fetch('/process', { method: 'POST', body: formData });
            const contentType = response.headers.get('content-type') || '';
            if (!response.ok) {
              let message = 'Zpracování selhalo. Zkuste to prosím znovu.';
              if (contentType.includes('application/json')) {
                const data = await response.json().catch(() => null);
                if (data && (data.detail || data.message)) {
                  message = data.detail || data.message;
                }
              } else {
                const text = await response.text().catch(() => '');
                if (text) message = text;
              }
              setNotice(message, 'error');
              return;
            }

            if (contentType.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')) {
              const blob = await response.blob();
              const url = window.URL.createObjectURL(blob);
              const disposition = response.headers.get('content-disposition') || '';
              const fileNameMatch = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
              const suggestedName = fileNameMatch ? decodeURIComponent(fileNameMatch[1] || fileNameMatch[2]) : 'valuagent.xlsx';
              const a = document.createElement('a');
              a.href = url; a.download = suggestedName; document.body.appendChild(a); a.click(); a.remove();
              window.URL.revokeObjectURL(url);
              setNotice('Excel byl úspěšně stažen.', 'success');
            } else if (contentType.includes('application/json')) {
              const data = await response.json();
              setNotice(data ? JSON.stringify(data) : 'Obdržena odpověď JSON.', 'success');
            } else {
              setNotice('Neznámá odpověď serveru.', 'error');
            }
          } catch (err) {
            setNotice('Chyba sítě. Zkontrolujte připojení a zkuste to znovu.', 'error');
          } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = previousText;
          }
        });
      })();
    </script>
  </body>
 </html>
"""


@router.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML)


@router.post("/process")
async def process_pdf(
    pdf: UploadFile = File(...),
    statement_type: str = Form(...),
    tolerance: int = Form(1),
    return_json: bool = Form(False),
):
    pdf_bytes = await pdf.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    model_obj = process_pdf_bytes(pdf_bytes, statement_type, tolerance)
    if return_json:
        return JSONResponse(model_obj.model_dump())

    excel_buffer = export_excel(statement_type, model_obj)
    filename = f"valuagent_{statement_type}_{model_obj.rok}.xlsx"
    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


