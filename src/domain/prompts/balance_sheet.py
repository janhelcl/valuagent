from string import Template

from src.shared import utils


BALANCE_SHEET_INDEX = utils.index_to_string(
    utils.read_balance_sheet_index()
)

balance_sheet_ocr_instructions = Template("""
Najdi v přiloženém PDF účetní rozvahu a indentifikuj její jednotlivé položky.

Existují následující položky:
Označení Položka
${balance_sheet_index}

Každá položka je sumou položek o jeden indent hlouběji.

Některé položky můžou v rozvaze chybět, pokud tomu tak je, vrať hodnoty 0.
V některých případech může být položka označena například zkratkou nebo synonymem.
Dej pozor na správné znaménko u jednotlivých položek. Kladná čísla vracej jako kladná, záporná čísla vracej jako záporná.
Dej pozor v jakých jednotkách je výkaz vyjádřen. Použij stejné jednotky ve výstupu.

Ke každé aktivní položce potřebujeme Brutto, Korekce, Netto a Netto v minulém období.
Pasivní položky jsou udávany pouze jedním stavem (Netto), potřebujeme tedy extrahovat Netto a Netto v minulém období.

Vracíš pouze json, nic jiného.
Jednotlivé položky označuj podle číselného sloupečku "Označení"
Formát:
{
    "rok": 2024,
    "data": {
        "1": {
            "brutto": 100000,
            "korekce": 10000,
            "netto": 90000,
            "netto_minule": 80000
        },
        "2": {
            "brutto": 50000,
            "korekce": 5000,
            "netto": 45000,
            "netto_minule": 40000
        },
        ...
        "78": {
            "netto": 90000,
            "netto_minule": 80000
        },
        ...
    }
""").safe_substitute(balance_sheet_index=BALANCE_SHEET_INDEX)


