// Exports Gen 4 game data from Pokémon Showdown (@pkmn/dex + @pkmn/data) into tracker/data/.
//
// You only need this to regenerate the data; the JSON files are committed to the repo.
//   cd tools/build_data
//   npm install
//   npm run build
//
// IDs match the game's own internal IDs (move 1-467, species 1-493, ability 1-123,
// held items), so data read from RAM can be looked up directly.

import {writeFileSync, mkdirSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {Dex} from '@pkmn/dex';
import {Generations} from '@pkmn/data';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'tracker', 'data');
const gen = new Generations(Dex).get(4);
const write = (name, data) => {
  writeFileSync(join(OUT, name), JSON.stringify(data, null, 1) + '\n');
  console.log(`wrote ${name}`);
};
mkdirSync(OUT, {recursive: true});

// ---- moves: indexed by in-game move ID. "Hidden Power <Type>" variants share ID 237 (and the
// same Showdown id); keep only plain Hidden Power.
const moves = {};
for (const m of gen.moves) {
  if (m.num < 1 || (m.num === 237 && m.name !== 'Hidden Power')) continue;
  moves[m.num] = {
    name: m.name,
    type: m.type,
    category: m.category,                       // Physical / Special / Status (Gen 4 split)
    power: m.basePower,
    accuracy: m.accuracy === true ? null : m.accuracy,   // null = never misses
    pp: m.pp,
    priority: m.priority,
    target: m.target,
    crit_ratio: m.critRatio ?? 1,
    multihit: m.multihit ?? null,               // number or [min, max]
    fixed_damage: m.damage ?? null,             // number, or "level" (Seismic Toss, Night Shade)
    recoil: m.recoil ?? null,                   // [numerator, denominator]
    drain: m.drain ?? null,
    flags: Object.keys(m.flags).sort(),         // contact, punch, sound, ...
  };
}

// ---- species: keyed by Showdown name ("Rotom-Wash"); forms lists names in the game's form order.
const species = {};
const byNum = {};
const addSpecies = s => {
  species[s.name] = {
    num: s.num,
    base_species: s.baseSpecies,
    forme: s.forme || null,
    types: s.types,
    base_stats: s.baseStats,                    // hp, atk, def, spa, spd, spe
    abilities: Object.values(s.abilities),
    weight_kg: s.weightkg,
    gender_ratio: s.genderRatio,
  };
};
for (const s of gen.species) {
  addSpecies(s);
  if (!s.forme) byNum[s.num] = {name: s.name, forms: [s.name]};
}
// Some forms exist in the game but aren't in the normal listing (e.g. Arceus-???): add them.
const formOrNull = n => {
  const s = gen.species.get(n);
  if (!s) return null;
  if (!species[s.name]) addSpecies(s);
  return s.name;
};
for (const entry of Object.values(byNum)) {
  const order = Dex.species.get(entry.name).formeOrder;
  if (order) entry.forms = order.map(formOrNull);
}
// Arceus: Gen 4 has the "???" form at index 9 (unused, hacking only) and no Fairy form.
// Showdown has no "???" form, so define it as Arceus with the ??? type.
if (byNum[493]) {
  species['Arceus-???'] = {...species['Arceus'], forme: '???', types: ['???']};
  const t = ['Normal', 'Fighting', 'Flying', 'Poison', 'Ground', 'Rock', 'Bug', 'Ghost', 'Steel', '???',
             'Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Ice', 'Dragon', 'Dark'];
  byNum[493].forms = t.map(x => (x === 'Normal' ? 'Arceus' : x === '???' ? 'Arceus-???' : formOrNull(`Arceus-${x}`)));
}

// ---- type chart: chart[attacking][defending] = multiplier
const typeNames = [...gen.types].map(t => t.name).filter(n => n !== '???').sort();
const chart = {};
for (const atk of typeNames) {
  chart[atk] = {};
  for (const def of typeNames) chart[atk][def] = gen.types.get(atk).effectiveness[def];
}

// ---- abilities and battle-relevant held items, by in-game ID
const abilities = {};
for (const a of gen.abilities) if (a.num > 0) abilities[a.num] = a.name;
const items = {};
for (const i of gen.items) {
  if (i.num <= 0) continue;
  items[i.num] = {name: i.name, fling_power: i.fling?.basePower ?? null,
                  natural_gift: i.naturalGift ?? null, is_berry: !!i.isBerry};
}

write('moves.json', moves);
write('species.json', {by_name: species, by_num: byNum});
write('types.json', chart);
write('abilities.json', abilities);
write('items.json', items);
write('meta.json', {source: 'Pokemon Showdown via @pkmn/dex + @pkmn/data', generation: 4,
                    versions: {'@pkmn/dex': '0.10.11', '@pkmn/data': '0.10.11'},
                    counts: {moves: Object.keys(moves).length, species: Object.keys(species).length,
                             abilities: Object.keys(abilities).length, items: Object.keys(items).length}});
