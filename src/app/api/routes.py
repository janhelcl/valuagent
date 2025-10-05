import os
import io
import zipfile
import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

logger = logging.getLogger(__name__)

from src.infrastructure.exporters.excel import export_excel
from src.infrastructure.exporters.dcf import export_dcf_template
from src.infrastructure.exporters.data_landing import export_data_landing
from src.services.process import process_pdf_bytes, disambiguate_pdf_bytes, process_pdf_bytes_async, disambiguate_pdf_bytes_async, ocr_and_validate_with_retries
from src.infrastructure import config


router = APIRouter()
security = HTTPBasic()


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("auth"))


def require_demo(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    # Allow if previously authenticated via form/cookie
    if is_authenticated(request):
        return
    demo_user = os.getenv("DEMO_USER", "demo")
    demo_pass = os.getenv("DEMO_PASSWORD", "")
    # If Authorization header is present, validate as Basic without redirect
    if request.headers.get("authorization"):
        if not (credentials.username == demo_user and credentials.password == demo_pass):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Basic"},
                detail="Unauthorized",
            )
        return
    # No session and no Authorization header → redirect to pretty login page
    raise HTTPException(status_code=307, headers={"Location": "/login"}, detail="Redirect")

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
      /* File list below dropzone */
      .file-list { list-style: none; margin: 8px 0 0 0; padding: 0; }
      .file-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
      .file-item + .file-item { margin-top: 6px; }
      .remove-btn { appearance: none; border: 0; background: transparent; color: #64748b; cursor: pointer; font-size: 16px; line-height: 1; padding: 2px 6px; border-radius: 6px; }
      .remove-btn:hover { background: #f1f5f9; color: #0f172a; }
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

      .aside { border-left: 1px solid #eef2f7; padding-left: 24px; display: flex; flex-direction: column; max-height: 600px; }
      @media (max-width: 920px) { .aside { border: 0; padding: 0; } }
      .list { margin: 0; padding-left: 18px; color: #222; }
      .list li { margin: 6px 0; color: #334155; }

      /* Chat log styles */
      .chat-log { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding: 12px; background: #f8fafc; border-radius: 12px; min-height: 200px; max-height: 500px; }
      .chat-message { display: flex; gap: 10px; align-items: flex-start; animation: slideIn 0.3s ease-out; }
      @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      .chat-avatar { width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), #1f57c7); display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
      .chat-message--system .chat-avatar { background: linear-gradient(135deg, #64748b, #475569); }
      .chat-message--success .chat-avatar { background: linear-gradient(135deg, #10b981, #059669); }
      .chat-message--error .chat-avatar { background: linear-gradient(135deg, #ef4444, #dc2626); }
      .chat-content { flex: 1; }
      .chat-text { background: #fff; padding: 10px 12px; border-radius: 8px; font-size: 14px; line-height: 1.5; color: #1e293b; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
      .chat-message--system .chat-text { background: #e2e8f0; color: #475569; }
      .chat-timestamp { font-size: 11px; color: #94a3b8; margin-top: 4px; }

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
              Vstupní soubory obsahující výkazy (PDF)
              <input id="file-input" type="file" name="pdfs" accept="application/pdf" multiple style="display:none" />
              <div id="dropzone" class="dropzone">
                <strong>Přetáhněte sem PDF soubory</strong>
                <div class="hint">nebo klikněte pro výběr</div>
                <div id="file-name" class="hint"></div>
              </div>
              <ul id="file-list" class="file-list" aria-live="polite"></ul>
            </label>
            <div class="hint">Typ výkazu bude rozpoznán automaticky (Rozvaha a/nebo VZZ) pro každý PDF soubor.</div>
            
            <label>
              Excel pro výstup
              <input id="template-input" type="file" name="excel_template" accept=".xlsx,.xls" style="display:none" />
              <div id="template-dropzone" class="dropzone">
                <strong>Přetáhněte sem Excel soubor</strong>
                <div class="hint">nebo klikněte pro výběr</div>
                <div id="template-file-name" class="hint"></div>
              </div>
              <ul id="template-file-list" class="file-list" aria-live="polite"></ul>
            </label>
            <div class="hint">Nahrajte Excel soubor s připravenými listy "Data - Rozvaha", "Data - Výsledovka" a "Data - Report Kvality"</div>

            <details class="settings">
              <summary>Nastavení</summary>
              <div class="settings-body">
                <input type="hidden" name="export_format" value="data_landing" />
                <label>
                  Offset
                  <input id="offset-input" type="number" name="offset" value="0" min="0" max="7" />
                  <div class="hint">Kolik období (let) zleva přeskočit. 0 = bez přeskočení (standardní), 1 = začít vyplňovat od druhého sloupce, atd. Užitečné když nejnovější data ještě nejsou k dispozici.</div>
                </label>
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
          <p class="section-title">Průběh zpracování</p>
          <div id="chat-log" class="chat-log">
            <div class="chat-message chat-message--system">
              <div class="chat-avatar">🤖</div>
              <div class="chat-content">
                <div class="chat-text">Ahoj! Jsem připraven zpracovat vaše účetní výkazy. Nahrajte PDF soubory a Excel template a klikněte na tlačítko Zpracovat.</div>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <div class="footer">Vaše soubory neukládáme. Zpracování je dočasné.</div>
    </div>

    <script>
      (function(){
        // Chat log functionality
        const chatLog = document.getElementById('chat-log');
        
        const addChatMessage = (text, type = 'info') => {
          const message = document.createElement('div');
          message.className = `chat-message chat-message--${type}`;
          
          const avatar = document.createElement('div');
          avatar.className = 'chat-avatar';
          avatar.textContent = type === 'error' ? '❌' : type === 'success' ? '✅' : '🤖';
          
          const content = document.createElement('div');
          content.className = 'chat-content';
          
          const textEl = document.createElement('div');
          textEl.className = 'chat-text';
          textEl.textContent = text;
          
          content.appendChild(textEl);
          message.appendChild(avatar);
          message.appendChild(content);
          chatLog.appendChild(message);
          
          // Auto-scroll to bottom
          chatLog.scrollTop = chatLog.scrollHeight;
        };
        
        const clearChatLog = () => {
          chatLog.innerHTML = '';
        };

        // PDF files handling (multiple files)
        const drop = document.getElementById('dropzone');
        const input = document.getElementById('file-input');
        const fileName = document.getElementById('file-name');
        const form = document.getElementById('upload-form');
        const submitBtn = document.getElementById('submit-btn');
        const notice = document.getElementById('notice');
        let selectedFiles = [];
        const listEl = document.getElementById('file-list');

        const renderList = () => {
          const files = selectedFiles.slice();
          if (files.length === 0) {
            fileName.textContent = '';
            listEl.innerHTML = '';
            return;
          }
          fileName.textContent = `${files.length} soubory`; // simple counter above
          listEl.innerHTML = '';
          for (const f of files) {
            const key = `${f.name}::${f.size}::${f.lastModified||0}`;
            const li = document.createElement('li');
            li.className = 'file-item';
            const nameSpan = document.createElement('span');
            nameSpan.textContent = f.name;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'remove-btn';
            btn.setAttribute('aria-label', `Odebrat ${f.name}`);
            btn.textContent = '×';
            btn.addEventListener('mousedown', (e) => { e.preventDefault(); e.stopPropagation(); });
            btn.addEventListener('click', (e) => {
              e.preventDefault();
              e.stopPropagation();
              selectedFiles = selectedFiles.filter(sf => `${sf.name}::${sf.size}::${sf.lastModified||0}` !== key);
              renderList();
            });
            li.appendChild(nameSpan);
            li.appendChild(btn);
            listEl.appendChild(li);
          }
        };
        const setNotice = (message, type) => {
          notice.textContent = message || '';
          notice.className = 'notice' + (type ? ` notice--${type}` : '');
        };

        const isPdf = (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf');
        const addFiles = (fileList) => {
          const incoming = Array.from(fileList || []);
          if (incoming.length === 0) return;
          if (!incoming.every(isPdf)) { 
            alert('Nahrajte prosím pouze soubory PDF.'); 
            addChatMessage('Musíte nahrát pouze PDF soubory.', 'error');
            return; 
          }
          const existing = new Set(selectedFiles.map(f => `${f.name}::${f.size}::${f.lastModified||0}`));
          const added = [];
          for (const f of incoming) {
            const key = `${f.name}::${f.size}::${f.lastModified||0}`;
            if (!existing.has(key)) { added.push(f); existing.add(key); }
          }
          if (added.length > 0) {
            selectedFiles = selectedFiles.concat(added);
            if (added.length === 1) {
              addChatMessage(`Přidán PDF soubor: ${added[0].name}`, 'info');
            } else {
              addChatMessage(`Přidáno ${added.length} PDF souborů.`, 'info');
            }
          }
          renderList();
        };

        drop.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); input.value = ''; input.click(); });
        drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('is-dragover'); });
        drop.addEventListener('dragleave', () => drop.classList.remove('is-dragover'));
        drop.addEventListener('drop', (e) => {
          e.preventDefault();
          drop.classList.remove('is-dragover');
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            addFiles(e.dataTransfer.files);
          }
        });
        input.addEventListener('change', () => { addFiles(input.files); input.value = ''; });

        // Excel template handling (single file only)
        const templateDrop = document.getElementById('template-dropzone');
        const templateInput = document.getElementById('template-input');
        const templateFileName = document.getElementById('template-file-name');
        const templateListEl = document.getElementById('template-file-list');
        let selectedTemplate = null;

        const renderTemplateList = () => {
          if (!selectedTemplate) {
            templateFileName.textContent = '';
            templateListEl.innerHTML = '';
            return;
          }
          templateFileName.textContent = '1 soubor';
          templateListEl.innerHTML = '';
          const li = document.createElement('li');
          li.className = 'file-item';
          const nameSpan = document.createElement('span');
          nameSpan.textContent = selectedTemplate.name;
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'remove-btn';
          btn.setAttribute('aria-label', `Odebrat ${selectedTemplate.name}`);
          btn.textContent = '×';
          btn.addEventListener('mousedown', (e) => { e.preventDefault(); e.stopPropagation(); });
          btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            selectedTemplate = null;
            renderTemplateList();
          });
          li.appendChild(nameSpan);
          li.appendChild(btn);
          templateListEl.appendChild(li);
        };

        const isExcel = (f) => {
          const name = f.name.toLowerCase();
          return name.endsWith('.xlsx') || name.endsWith('.xls') || 
                 f.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                 f.type === 'application/vnd.ms-excel';
        };
        
        const setTemplate = (fileList) => {
          const incoming = Array.from(fileList || []);
          if (incoming.length === 0) return;
          if (incoming.length > 1) { 
            alert('Nahrajte prosím pouze jeden Excel soubor.'); 
            addChatMessage('Můžete nahrát pouze jeden Excel template.', 'error');
            return; 
          }
          if (!isExcel(incoming[0])) { 
            alert('Nahrajte prosím Excel soubor (.xlsx nebo .xls).'); 
            addChatMessage('Soubor musí být ve formátu Excel (.xlsx nebo .xls).', 'error');
            return; 
          }
          selectedTemplate = incoming[0];
          addChatMessage(`Excel template nahrán: ${selectedTemplate.name}`, 'info');
          renderTemplateList();
        };

        templateDrop.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); templateInput.value = ''; templateInput.click(); });
        templateDrop.addEventListener('dragover', (e) => { e.preventDefault(); templateDrop.classList.add('is-dragover'); });
        templateDrop.addEventListener('dragleave', () => templateDrop.classList.remove('is-dragover'));
        templateDrop.addEventListener('drop', (e) => {
          e.preventDefault();
          templateDrop.classList.remove('is-dragover');
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setTemplate(e.dataTransfer.files);
          }
        });
        templateInput.addEventListener('change', () => { setTemplate(templateInput.files); templateInput.value = ''; });

        // Form submission
        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          setNotice('', '');
          if (selectedFiles.length === 0) {
            setNotice('Nahrajte prosím alespoň jeden PDF soubor.', 'error');
            addChatMessage('Chyba: Nejsou nahrány žádné PDF soubory.', 'error');
            return;
          }
          
          // Check if template is provided
          if (!selectedTemplate) {
            setNotice('Nahrajte prosím Excel template.', 'error');
            addChatMessage('Chyba: Není nahrán Excel template.', 'error');
            return;
          }
          
          // Clear previous messages and start processing
          clearChatLog();
          addChatMessage(`Výborně! Mám ${selectedFiles.length} ${selectedFiles.length === 1 ? 'PDF soubor' : selectedFiles.length < 5 ? 'PDF soubory' : 'PDF souborů'} a Excel template.`, 'info');
          
          submitBtn.disabled = true;
          const previousText = submitBtn.textContent;
          submitBtn.textContent = 'Zpracovávám…';
          
          try {
            const formData = new FormData(form);
            // Rebuild PDF files from selectedFiles
            formData.delete('pdfs');
            const filesToSend = selectedFiles.slice();
            for (const f of filesToSend) formData.append('pdfs', f, f.name);
            // Add template
            formData.delete('excel_template');
            if (selectedTemplate) formData.append('excel_template', selectedTemplate, selectedTemplate.name);
            
            // Use SSE for real-time progress
            const response = await fetch('/process-stream', { method: 'POST', body: formData });
            
            if (!response.ok) {
              const text = await response.text().catch(() => '');
              setNotice(text || 'Zpracování selhalo', 'error');
              addChatMessage(`Chyba: ${text || 'Zpracování selhalo'}`, 'error');
              return;
            }
            
            // Read SSE stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let downloadData = null;
            
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              
              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\\n\\n');
              buffer = lines.pop() || '';
              
              for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = JSON.parse(line.substring(6));
                
                if (data.type === 'download') {
                  // Store download data for later
                  downloadData = data;
                } else {
                  // Regular progress message
                  addChatMessage(data.message, data.type || 'info');
                }
              }
            }
            
            // Trigger download if we have data
            if (downloadData) {
              const blob = base64ToBlob(downloadData.data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = downloadData.filename;
              document.body.appendChild(a);
              a.click();
              a.remove();
              window.URL.revokeObjectURL(url);
              setNotice('Excel byl úspěšně stažen.', 'success');
            }
          } catch (err) {
            setNotice('Chyba sítě. Zkontrolujte připojení a zkuste to znovu.', 'error');
            addChatMessage('Chyba připojení k serveru. Zkontrolujte prosím své internetové připojení.', 'error');
          } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = previousText;
          }
        });
        
        // Helper function to convert base64 to Blob
        function base64ToBlob(base64, mimeType) {
          const byteCharacters = atob(base64);
          const byteArrays = [];
          for (let i = 0; i < byteCharacters.length; i++) {
            byteArrays.push(byteCharacters.charCodeAt(i));
          }
          return new Blob([new Uint8Array(byteArrays)], { type: mimeType });
        }
      })();
    </script>
  </body>
 </html>
"""


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")
    return HTMLResponse(INDEX_HTML)


from src.app.main import limiter  # import limiter for decorators


@router.post("/process")
@limiter.limit("10/minute")
async def process_pdf(
    request: Request,
    pdfs: list[UploadFile] = File(...),
    tolerance: int = Form(1),
    return_json: bool = Form(False),
    ocr_retries: int = Form(None),
    export_format: str = Form("data_landing"),  # Always use data_landing format
    excel_template: UploadFile = File(None),  # Required Excel template for data_landing format
    offset: int = Form(0),  # Number of years to skip from the left (data_landing only)
):
    if not is_authenticated(request):
        return JSONResponse({"detail": "Nejste přihlášeni."}, status_code=401)

    # Read files and validate
    file_payloads: list[tuple[str, bytes]] = []
    logger.info(f"Processing {len(pdfs)} uploaded PDF files")
    
    for i, f in enumerate(pdfs):
        content = await f.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Uploaded file '{f.filename}' is empty")
        filename = f.filename or f"soubor_{i+1}.pdf"
        file_payloads.append((filename, content))
        logger.info(f"File {i+1}: {filename} ({len(content)/1024:.1f}KB)")

    import asyncio
    
    # Process all files concurrently using async
    async def process_single_file(original_name: str, pdf_bytes: bytes):
        logger.info(f"Starting processing of file: {original_name}")
        
        # First disambiguate what's in the file
        info = await disambiguate_pdf_bytes_async(pdf_bytes)
        present_types: list[str] = []
        if info.get("rozvaha"):
            present_types.append("rozvaha")
        if info.get("vzz"):
            present_types.append("vzz")
        if not present_types:
            logger.error(f"No statement types detected in {original_name}")
            raise HTTPException(status_code=400, detail=f"Ve souboru '{original_name}' nebyl rozpoznán Rozvaha ani VZZ")

        logger.info(f"File {original_name} contains: {present_types}")

        # Determine max retries
        max_retries = ocr_retries if ocr_retries is not None else config.get_ocr_max_retries()
        if not isinstance(max_retries, int):
            max_retries = config.get_ocr_max_retries()
        if max_retries < 1:
            max_retries = 1
        if max_retries > 5:
            max_retries = 5

        # Process each statement type concurrently with retries
        tasks = []
        for st_type in present_types:
            logger.debug(f"Creating task for {original_name} - {st_type} with up to {max_retries} OCR attempts")
            tasks.append(ocr_and_validate_with_retries(pdf_bytes, st_type, tolerance, max_retries))
        
        logger.info(f"Processing {len(tasks)} statement types for {original_name}")
        models = await asyncio.gather(*tasks)
        
        file_results = []
        for st_type, result_obj in zip(present_types, models):
            # result_obj is the dict from ocr_and_validate_with_retries
            result_obj = dict(result_obj)
            result_obj["original"] = original_name
            result_obj["statement_type"] = st_type
            result_obj["disambiguation_info"] = info
            file_results.append(result_obj)
            logger.debug(f"Completed {st_type} for {original_name} with status {result_obj.get('status')}")
        
        logger.info(f"Finished processing file: {original_name} ({len(file_results)} results)")
        return file_results

    # Process all files concurrently
    logger.info(f"Starting concurrent processing of {len(file_payloads)} files")
    file_tasks = [process_single_file(name, bytes_) for name, bytes_ in file_payloads]
    file_results_lists = await asyncio.gather(*file_tasks)
    
    # Flatten the results
    results = []
    for file_results in file_results_lists:
        results.extend(file_results)
    
    logger.info(f"All processing completed. Total results: {len(results)}")

    if return_json:
        # Return compact JSON summary
        payload = [
            {
                "file": r.get("original"),
                "statement_type": r.get("statement_type"),
                "rok": getattr(r.get("model"), "rok", None) if r.get("model") is not None else (r.get("raw") or {}).get("rok"),
                "rows": len(getattr(r.get("model"), "data", {})) if r.get("model") is not None else len((r.get("raw") or {}).get("data", {})),
                "ocr_attempts": r.get("ocr_attempts", 1),
                "status": r.get("status", "ok"),
                "validation_errors_count": len(r.get("validation_errors") or []),
            }
            for r in results
        ]
        return JSONResponse(payload)

    # Choose export format based on parameter
    if export_format == "data_landing":
        # Export using new data landing format - requires Excel template
        if not excel_template or not excel_template.filename:
            raise HTTPException(
                status_code=400, 
                detail="Pro formát 'data_landing' je vyžadován Excel template. Nahrajte prosím Excel soubor."
            )
        
        try:
            logger.info(f"Creating data landing export using template: {excel_template.filename}")
            
            # Read the Excel template
            template_content = await excel_template.read()
            if not template_content:
                raise HTTPException(status_code=400, detail="Nahrán prázdný Excel template")
            
            logger.info(f"Read Excel template: {len(template_content)/1024:.1f}KB")
            
            # Get year for filename
            balance_sheets = [r for r in results if r["statement_type"] == "rozvaha"]
            if balance_sheets:
                latest_bs = max(balance_sheets, key=lambda x: getattr(x["model"], "rok", 0))
                year = getattr(latest_bs["model"], "rok", "")
                filename = f"Data_valuagent_{year}.xlsx"
            else:
                filename = "Data_valuagent.xlsx"
            
            data_buffer = export_data_landing(results, template_content, tolerance=tolerance, offset=offset)
            
            logger.info(f"Generated data landing export: {filename}")
            return StreamingResponse(
                data_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
            
        except ValueError as e:
            # Handle template validation errors
            logger.error(f"Template validation error: {e}")
            raise HTTPException(status_code=400, detail=f"Chyba v template: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to create data landing export: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Selhalo vytvoření exportu: {str(e)}")
    
    # Default: Export using DCF template with Předmět ocenění sheet filled
    try:
        logger.info("Creating DCF template export")
        
        # Get disambiguation info from the latest balance sheet result
        balance_sheets = [r for r in results if r["statement_type"] == "rozvaha"]
        disambiguation_info = None
        if balance_sheets:
            latest_bs = max(balance_sheets, key=lambda x: getattr(x["model"], "rok", 0))
            disambiguation_info = latest_bs.get("disambiguation_info")
            year = getattr(latest_bs["model"], "rok", "")
            filename = f"DCF_valuagent_{year}.xlsx"
        else:
            filename = "DCF_valuagent.xlsx"
        
        dcf_buffer = export_dcf_template(results, disambiguation_info, tolerance=tolerance)
        
        logger.info(f"Generated DCF template: {filename}")
        return StreamingResponse(
            dcf_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
        
    except Exception as e:
        logger.error(f"Failed to create DCF template: {e}", exc_info=True)
        # Fallback to old behavior if DCF template fails
        logger.info("Falling back to ZIP export due to DCF template error")
        
        # If only one Excel, return it directly for convenience
        if len(results) == 1:
            logger.info("Returning single Excel file (fallback)")
            r0 = results[0]
            st_type = r0["statement_type"]
            model_obj = r0["model"]
            excel_buffer = export_excel(st_type, model_obj)
            safe_name = (r0["original"] or "valuagent").rsplit(".", 1)[0]
            filename = f"{safe_name}_{st_type}_{model_obj.rok}.xlsx"
            logger.info(f"Generated Excel file: {filename}")
            return StreamingResponse(
                excel_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        # Otherwise bundle into a ZIP
        logger.info(f"Creating ZIP file with {len(results)} Excel files (fallback)")
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, r in enumerate(results):
                st_type = r["statement_type"]
                model_obj = r["model"]
                logger.debug(f"Generating Excel {i+1}/{len(results)}: {r['original']} - {st_type}")
                excel_buffer = export_excel(st_type, model_obj)
                safe_name = (r["original"] or "valuagent").rsplit(".", 1)[0]
                arcname = f"{safe_name}_{st_type}_{model_obj.rok}.xlsx"
                zf.writestr(arcname, excel_buffer.getvalue())
        zip_buf.seek(0)

        logger.info(f"ZIP file created with {len(results)} files, size: {zip_buf.getbuffer().nbytes/1024:.1f}KB")
        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=valuagent_results.zip"},
    )


@router.post("/process-stream")
@limiter.limit("10/minute")
async def process_pdf_stream(
    request: Request,
    pdfs: list[UploadFile] = File(...),
    tolerance: int = Form(1),
    ocr_retries: int = Form(None),
    excel_template: UploadFile = File(None),
    offset: int = Form(0),
):
    """Process PDFs with real-time progress updates via Server-Sent Events"""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Nejste přihlášeni.")

    import json
    import base64
    import asyncio

    # Read all files BEFORE creating the generator (UploadFile objects will be closed after this function scope)
    logger.info(f"Reading {len(pdfs)} uploaded PDF files")
    file_payloads: list[tuple[str, bytes]] = []
    for i, f in enumerate(pdfs):
        content = await f.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Uploaded file '{f.filename}' is empty")
        filename = f.filename or f"soubor_{i+1}.pdf"
        file_payloads.append((filename, content))
        logger.info(f"File {i+1}: {filename} ({len(content)/1024:.1f}KB)")

    # Read template
    if not excel_template or not excel_template.filename:
        raise HTTPException(status_code=400, detail="Excel template is required")
    
    template_content = await excel_template.read()
    if not template_content:
        raise HTTPException(status_code=400, detail="Excel template is empty")
    
    template_filename = excel_template.filename
    logger.info(f"Excel template read: {template_filename} ({len(template_content)/1024:.1f}KB)")

    async def event_generator():
        try:
            # Helper to send SSE message
            def send_event(message: str, event_type: str = "info"):
                return f"data: {json.dumps({'message': message, 'type': event_type})}\n\n"

            yield send_event(f"Načítám {len(file_payloads)} {'soubor' if len(file_payloads) == 1 else 'soubory' if len(file_payloads) < 5 else 'souborů'}...")

            # Report loaded files
            for filename, content in file_payloads:
                yield send_event(f"✓ Načten: {filename} ({len(content)/1024:.1f} KB)")
            
            yield send_event(f"✓ Excel template načten: {template_filename}")
            
            # Determine max retries
            max_retries = ocr_retries if ocr_retries is not None else config.get_ocr_max_retries()
            if not isinstance(max_retries, int):
                max_retries = config.get_ocr_max_retries()
            max_retries = max(1, min(max_retries, 5))

            # Process all files concurrently
            yield send_event(f"🚀 Spouštím paralelní zpracování {len(file_payloads)} {'souboru' if len(file_payloads) == 1 else 'souborů'}...")
            
            async def process_single_file(original_name: str, pdf_bytes: bytes, file_idx: int):
                """Process a single file and yield progress events"""
                results = []
                
                # Disambiguate
                info = await disambiguate_pdf_bytes_async(pdf_bytes)
                
                present_types: list[str] = []
                if info.get("rozvaha"):
                    present_types.append("rozvaha")
                if info.get("vzz"):
                    present_types.append("vzz")
                
                if not present_types:
                    return []  # No statements found
                
                detected = ", ".join(["Rozvaha" if t == "rozvaha" else "Výkaz zisku a ztráty" for t in present_types])
                
                # Process each statement type concurrently
                tasks = []
                for st_type in present_types:
                    tasks.append(ocr_and_validate_with_retries(pdf_bytes, st_type, tolerance, max_retries))
                
                statement_results = await asyncio.gather(*tasks)
                
                for st_type, result_obj in zip(present_types, statement_results):
                    result_obj = dict(result_obj)
                    result_obj["original"] = original_name
                    result_obj["statement_type"] = st_type
                    result_obj["disambiguation_info"] = info
                    results.append(result_obj)
                
                return results
            
            # Create tasks for all files
            file_tasks = [
                process_single_file(name, bytes_, idx + 1) 
                for idx, (name, bytes_) in enumerate(file_payloads)
            ]
            
            # Process with progress tracking
            all_results = []
            completed = 0
            for task in asyncio.as_completed(file_tasks):
                file_results = await task
                completed += 1
                
                if file_results:
                    first_result = file_results[0]
                    original_name = first_result.get("original", "?")
                    detected_types = [r.get("statement_type") for r in file_results]
                    detected_names = [("Rozvaha" if t == "rozvaha" else "VZZ") for t in detected_types]
                    
                    for result in file_results:
                        st_type = result.get("statement_type")
                        st_name = "Rozvaha" if st_type == "rozvaha" else "VZZ"
                        
                        if result.get("status") == "ok":
                            model = result.get("model")
                            rok = getattr(model, "rok", "?")
                            attempts = result.get("ocr_attempts", 1)
                            data_rows = len(getattr(model, "data", {}))
                            yield send_event(f"✅ {original_name} - {st_name}: rok {rok}, {data_rows} řádků ({completed}/{len(file_payloads)} hotovo)")
                        else:
                            yield send_event(f"⚠ {original_name} - {st_name}: zpracováno s chybami", "error")
                    
                    all_results.extend(file_results)
                else:
                    yield send_event(f"⚠ Soubor {completed}/{len(file_payloads)}: žádný výkaz rozpoznán", "error")
            
            if not all_results:
                yield send_event("Žádné výkazy nebyly úspěšně zpracovány", "error")
                return
            
            # Create Excel
            yield send_event("📊 Vytvářím Excel soubor s vašimi daty...")
            
            balance_sheets = [r for r in all_results if r["statement_type"] == "rozvaha"]
            if balance_sheets:
                latest_bs = max(balance_sheets, key=lambda x: getattr(x["model"], "rok", 0))
                year = getattr(latest_bs["model"], "rok", "")
                filename = f"Data_valuagent_{year}.xlsx"
            else:
                filename = "Data_valuagent.xlsx"
            
            data_buffer = export_data_landing(all_results, template_content, tolerance=tolerance, offset=offset)
            
            # Convert buffer to base64 for transmission
            excel_b64 = base64.b64encode(data_buffer.getvalue()).decode('utf-8')
            
            yield send_event("✅ Excel soubor je připraven ke stažení!", "success")
            yield f"data: {json.dumps({'type': 'download', 'filename': filename, 'data': excel_b64})}\n\n"
            yield send_event("🎉 Hotovo! Můžete zpracovat další výkazy.", "success")
            
        except Exception as e:
            logger.error(f"Error in processing stream: {e}", exc_info=True)
            yield send_event(f"Chyba při zpracování: {str(e)}", "error")
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Pretty login page (form-based)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang=\"cs\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Přihlášení – Valuagent</title>
    <style>
      :root { --bg:#0b1020; --card:#fff; --text:#0b1020; --muted:#5b6479; --primary:#2b6ef6; --ring: rgba(43,110,246,.3); }
      html, body { height:100%; }
      body { margin:0; padding:32px; display:grid; place-items:center; background: radial-gradient(1200px 600px at 20% -10%, #233161, transparent 60%), radial-gradient(1000px 600px at 100% 0%, #1f2a52, transparent 50%), var(--bg); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; }
      .card { width: 100%; max-width: 480px; background: var(--card); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(16,24,40,.18); }
      .header { display:flex; align-items:center; gap:12px; color:#1e293b; margin-bottom:10px; }
      .header img { height:48px; width:48px; border-radius:10px; background:#fff; padding:6px; }
      h1 { font-size: 22px; margin:0; }
      p { margin: 4px 0 0 0; color:#64748b; }
      form { display:grid; gap:12px; margin-top:16px; }
      label { color:#475569; font-size:14px; display:grid; gap:6px; }
      input { border:1px solid #e5e7eb; border-radius:10px; padding:10px 12px; font-size:16px; }
      input:focus { outline:none; border-color: var(--primary); box-shadow: 0 0 0 4px var(--ring); }
      button { background: var(--primary); color:#fff; border:0; border-radius:10px; padding:10px 16px; font-weight:600; cursor:pointer; }
      .hint { font-size:12px; color:#64748b; }
      .error { color:#b91c1c; font-size:14px; }
    </style>
  </head>
  <body>
    <div class=\"card\">
      <div class=\"header\">
        <img src=\"/static/logo.png\" alt=\"Valuagent\" onerror=\"this.style.display='none'\" />
        <div>
          <h1>Přihlášení</h1>
          <p>Použijte přístup pro demo.</p>
        </div>
      </div>
      <form method=\"post\" action=\"/login\" autocomplete=\"off\">
        <label>Uživatel <input type=\"text\" name=\"username\" value=\"demo\" required /></label>
        <label>Heslo <input type=\"password\" name=\"password\" /></label>
        <button type=\"submit\">Přihlásit</button>
        <div class=\"hint\">Pokud nemáte přístup, kontaktujte nás.</div>
      </form>
    </div>
  </body>
 </html>
"""


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/")
    return HTMLResponse(LOGIN_HTML)


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form("")):
    demo_user = os.getenv("DEMO_USER", "demo")
    demo_pass = os.getenv("DEMO_PASSWORD", "")
    if username == demo_user and password == demo_pass:
        request.session["auth"] = True
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(LOGIN_HTML.replace("</form>", "<div class=\"error\">Neplatné přihlašovací údaje</div></form>"), status_code=401)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")
