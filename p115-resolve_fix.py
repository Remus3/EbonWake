import re


def sub(path, repls):
    s = open(path, newline='').read()
    pat = re.compile(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> refs/ew/keep/115\n', re.S)
    i = [0]

    def f(m):
        r = repls[i[0]]
        i[0] += 1
        return r
    s = pat.sub(f, s)
    assert i[0] == len(repls)
    open(path, 'w', newline='').write(s)


sub('app/shared/core/ocr.part.js', [
    "  // Plan 113: + loot {name, count, id, source} (a fix is the count).\n"
    "  // Plan 115: + currency_balance (name = event number, value = balance).\n"
    "  const OCR_AUTO_KINDS = ['silver', 'buff', 'level', 'gear', 'book_use', 'loot',\n"
    "    'currency_balance'];\n"
    "  const OCR_LOOT_MAX = 1e7;  // server grind.MAX_LOOT_COUNT\n",
    "      gear: 'stat 0-999', loot: 'count', currency_balance: 'balance at the shot' }[kind] || '';\n",
    "    if (kind === 'loot' && (v < 1 || v > OCR_LOOT_MAX)) return null;\n"
    "    if (kind === 'currency_balance' && v > 1e7) return null;\n",
])
sub('server/ew/app.py', [
    "            catalog=self.names.catalog,  # plan 113: off-table loot names\n"
    "            currency=self.currency)  # plan 115: exchange / tooltip -> event currency balance\n"
    "        # Plan 081: the running session's OCR loot counts prefill the loot form;\n"
    "        # plan 113: an auto session closes with them as its loot, cache-priced.\n",
])
sub('server/ew/ocrauto.py', [
    "# Plan 113: a loot-window row (table or catalog item + count) under the gate.\n"
    "# Plan 115: an event currency balance (exchange window / tooltip) -> eventcurrency.\n"
    "CURRENCY_KIND = \"currency_balance\"\n"
    "KINDS = (\"silver\", \"buff\", \"level\", \"gear\", \"book_use\") + PLANNER_KINDS + (\n"
    "    zoneinfo.KIND, \"loot\", CURRENCY_KIND)\n"
    "# a book suggestion and a zone read are accept / discard only; a loot fix is a count\n"
    "FIX_KINDS = (\"silver\", \"buff\", \"level\", \"gear\") + PLANNER_KINDS + (\"loot\", CURRENCY_KIND)\n"
    "LOOT_KEYS = {\"name\", \"count\", \"id\", \"source\", \"spot\", \"started\"}\n"
    "LOOT_SOURCES = (\"table\", \"catalog\")\n",
    "                 loot_target=None, zones=None, bosses=None, catalog=None, currency=None):\n",
    "@@A@@\n",
    "@@B@@\n",
])
