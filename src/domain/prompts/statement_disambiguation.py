statement_disambiguation_instructions = """
Přečti přiložené PDF. 

Identifikuj, zda obsahuje Rozvahu a Výkaz zisku a ztráty. Může obsahovat obojí.
Dále identifikuj datum ke kterému jsou výkazy vydány.

POZOR: nepleť si datum ke kterému jsou výkazy vydány s datumem kdy jsou zveřejněny. Tyto pojmy jsou odlišné.

Vracíš pouze json, nic jiného.
Formát:
{
    "rozvaha": true, # true nebo false
    "výkaz_zisku_a_ztráty": true, # true nebo false
    "datum": "2024-01-01" # datum ve formátu YYYY-MM-DD
}
"""