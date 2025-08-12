from string import Template

from src.shared import utils


PROFIT_AND_LOSS_INDEX = utils.index_to_string(
    utils.read_profit_and_loss_index()
)

profit_and_loss_ocr_instructions = Template("""
Najdi v přiloženém PDF účetní výkaz zisku a ztráty a indentifikuj jeho jednotlivé položky.

Existují následující položky:
Označení Položka
${profit_and_loss_index}

Každá položka je sumou položek o jeden indent hlouběji.
Dej pozor na správné znaménko u jednotlivých položek. Kladná čísla vracej jako kladná, záporná čísla vracej jako záporná.
Dej pozor v jakých jednotkách je výkaz vyjádřen. Použij stejné jednotky ve výstupu.

Některé položky můžou ve výkazu zisku a ztráty chybět, pokud tomu tak je, vrať hodnoty 0.
Ke každé položce potřebujeme současné a minulé období.

Vracíš pouze json, nic jiného.
Formát:
{
    "rok": 2024,
    "data": {
        "1": {
            "současné": 100000,
            "minulé": 80000
        },
        "2": {
            "současné": 50000,
            "minulé": 40000
        },
        ...
    }
}
""").safe_substitute(profit_and_loss_index=PROFIT_AND_LOSS_INDEX)


