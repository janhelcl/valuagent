statement_disambiguation_instructions = """
Přečti přiložené PDF. 

Identifikuj, zda obsahuje Rozvahu a Výkaz zisku a ztráty. Může obsahovat obojí.
Dále identifikuj datum ke kterému je zpracována účetní závěrka.

POZOR: Soubor může obsahovat celou řadu datumů. Nás zajíma datum ke kterému je zpracována účetní závěrka, to znamená poslední den daného účetního období. Typicky se uvádí v hlavičce každého z výkazů.
Neplést si s ostatními datumy v souboru, jako je například datum kdy jsou výkazy zveřejněny.

Vracíš pouze json, nic jiného.
Formát:
{
    "rozvaha": true, # true nebo false
    "výkaz_zisku_a_ztráty": true, # true nebo false
    "datum": "2024-01-01" # datum ve formátu YYYY-MM-DD
}
"""