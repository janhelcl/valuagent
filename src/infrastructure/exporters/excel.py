import io


def export_excel(statement_type: str, model) -> io.BytesIO:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"

    headers = (
        ["Označení", "Brutto", "Korekce", "Netto", "Netto (minulé)"]
        if statement_type == "rozvaha"
        else ["Označení", "Současné", "Minulé"]
    )
    for idx, name in enumerate(headers, start=1):
        ws.cell(row=1, column=idx, value=name)

    for r_idx, (row_id, row_obj) in enumerate(sorted(model.data.items(), key=lambda kv: kv[0]), start=2):
        ws.cell(row=r_idx, column=1, value=row_id)
        if statement_type == "rozvaha":
            ws.cell(row=r_idx, column=2, value=getattr(row_obj, "brutto", None))
            ws.cell(row=r_idx, column=3, value=getattr(row_obj, "korekce", None))
            ws.cell(row=r_idx, column=4, value=getattr(row_obj, "netto", 0))
            ws.cell(row=r_idx, column=5, value=getattr(row_obj, "netto_minule", 0))
        else:
            ws.cell(row=r_idx, column=2, value=getattr(row_obj, "současné", 0))
            ws.cell(row=r_idx, column=3, value=getattr(row_obj, "minulé", 0))

    report = wb.create_sheet("Report")
    report_text = model.summary_report()
    for i, line in enumerate(report_text.splitlines(), start=1):
        report.cell(row=i, column=1, value=line)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


