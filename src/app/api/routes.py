from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from src.infrastructure.exporters.excel import export_excel
from src.services.process import process_pdf_bytes


router = APIRouter()

INDEX_HTML = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Valuagent</title>
    <style>
      body { font-family: system-ui, Arial, sans-serif; margin: 2rem; }
      form { display: grid; gap: .75rem; max-width: 560px; }
      input, select, button { padding: .6rem; font-size: 1rem; }
    </style>
  </head>
  <body>
    <h2>Valuagent – Extract and Validate</h2>
    <form id=\"f\" action=\"/process\" method=\"post\" enctype=\"multipart/form-data\">
      <label>PDF <input type=\"file\" name=\"pdf\" accept=\"application/pdf\" required /></label>
      <label>Statement type
        <select name=\"statement_type\" required>
          <option value=\"rozvaha\">Rozvaha</option>
          <option value=\"vzz\">Výkaz zisku a ztráty</option>
        </select>
      </label>

      <label>Tolerance <input type=\"number\" name=\"tolerance\" value=\"0\" /></label>
      <button type=\"submit\">Process</button>
    </form>
    <p>Response will download as Excel if successful.</p>
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
    tolerance: int = Form(0),
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


