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
    "            elif kind == \"loot\":\n"
    "                cur = self.store.get(\"ocr_loot\")\n"
    "                if (_ts(cur.get(\"started\")) or 0) > _ts(value[\"started\"]):\n"
    "                    raise ValueError(\"that grind session's loot was replaced by a newer one\")\n"
    "                row = {\"name\": value[\"name\"], \"count\": value[\"count\"], \"confidence\": 1.0,\n"
    "                       \"id\": value[\"id\"], \"source\": value[\"source\"]}\n"
    "                prev = self._loot_put(value[\"spot\"], value[\"started\"], [row], shot_at, file)\n"
    "                if value[\"name\"] not in prev:\n"
    "                    raise ValueError(f\"{value['name']} has a newer read\")\n"
    "                items = self.store.get(\"ocr_loot\").get(\"items\") or {}\n"
    "                entry.update(prev=prev[value[\"name\"]], written=items.get(value[\"name\"]))\n"
    "            elif kind == CURRENCY_KIND:\n"
    "                # Plan 115: the balance as read at the shot (a fix too: it corrects the read).\n"
    "                entry[\"prev\"] = self._need(self.currency).set_balance(\n"
    "                    name, value, source=f\"ocr:{_str(file, 255)}\", at=shot_at, uid=uid)\n",
    "            elif c.get(\"kind\") == \"loot\":\n"
    "                v = c.get(\"value\") if isinstance(c.get(\"value\"), dict) else {}\n"
    "                self._loot_restore(v.get(\"spot\"), v.get(\"started\"), v.get(\"name\"),\n"
    "                                   c.get(\"written\"), c.get(\"prev\"))\n"
    "            elif c.get(\"kind\") == CURRENCY_KIND:\n"
    "                self._need(self.currency).restore_read(c.get(\"name\"), uid, c.get(\"prev\"))\n",
])
