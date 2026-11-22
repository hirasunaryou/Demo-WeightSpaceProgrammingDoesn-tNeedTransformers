# A hand-written second-order association memory for ARC science questions (generation 5)

Generation 5 keeps the generation-4 design and compiler. It adds about 2,500 hand-written knowledge lines
(`facts_g5_*.txt`) and six mechanism changes, described in "What generation 5 changed" at the end. The
generation-4 text follows unchanged.

---

# Generation 4 notes (unchanged)

Generation 4 keeps the generation-3 design and compiler. It adds about 2,500 hand-written knowledge lines
(`facts_g4_*.txt`) and five mechanism changes, described in "What generation 4 changed" at the end. The
generation-3 text follows unchanged.

Nothing here is trained or fitted. Every word and every association was written by hand in `kb/`;
`build.py` turns that text into the tensors `arch.py` expects. It uses fixed formulas, and their constants
were chosen by reasoning about what each part should do. They are listed with a comment each at the top of
`build.py`. Generation 3 keeps the generation-2 design and compiler, adds about 2,500 lines of knowledge
(`facts_g3_*.txt`), and changes the mechanism where reading per-option explanations on invented questions showed
a systematic fault. Those changes are listed under "What generation 3 changed" below. The generation-2 sections
follow unchanged except for numbers that have since changed.

## What the knowledge looks like (`kb/`)

| file | content |
|---|---|
| `facts_*.txt` (parent, ≈ 5,400 lines) | grade 3–9 science by topic: Earth, space, life, body, physics, chemistry, inquiry and safety, technology, environment, everyday objects, typical question scenarios |
| `facts_g2_*.txt` (new, ≈ 2,500 lines) | question pattern → answer rules for Earth/weather/water/rocks/soil, space, life science, body, physical science, chemistry, inquiry and engineering, scenarios ("which best explains"), cause → effect chains, organisms, scientists and inventions, earth history, "function of X", and **misconceptions** that ARC distractors use (`seasons cause >! distance closer farther`) |
| `facts_g3_*.txt` (new, ≈ 2,500 lines) | matter and chemistry, energy/forces/waves/electricity, Earth and weather, space, life, ecology and resources, body and health, inquiry/tools/safety/engineering, facts as state tests ask them, classroom investigations and their usual results, paraphrases of frequent facts, regional facts and everyday estimates, rules using the new *in/out* and *without* concepts (`facts_g3_direction.txt`), and **distractor traps** (`facts_g3_traps.txt`: `sound travels fastest >! vacuum air`) |
| `facts_g2_links.txt` | links between base words and the derived words that are now their own concepts (see below) |
| `tax.txt` | taxonomy `parent: child, ...`; generation 2 adds everyday categories (colors, seasons, metals, fuels, storms, conductors and insulators, physical and chemical changes, landforms, lab tools, pollinators, ...) |
| `same.txt` | morphology; `!word` keeps a word as its own concept |
| `stop.txt`, `common.txt`, `adj.txt` | function words, general words with a capped weight, comparatives |

Line formats: `cues > answers` (directed), `term = definition` (both ways), `cues >! answers` (evidence against),
plain lines (topic cluster, symmetric and weaker). `#` starts a comment.

## From text to weights (`build.py`): the parent's pipeline

* A stemmer plus `same.txt` maps words to concepts (`vocab.txt` ≈ 44k words, ≈ 4,150 concepts; run
  `python build.py --vocab` after editing `kb/`).
* idf comes from document frequency over the fact lines. General words are capped at 0.8 and `not`/`except` get 4.5.
* First-order `A`: rule weights scaled by 1/√(#cues) and √(2/#answers); answers support cues at 0.3; taxonomy
  closure; hub damping; and a global two-hop term.
* Pair table (generation 3: H = 2^22 rows × R = 16): every pair of cues in a rule recalls its answers. Recalls that
  add up through one pair grow sublinearly.

## What generation 2 changed, and why

1. **Derived words that are answers are their own concepts.** The architecture drops any option concept that the
   question also has. The parent merged *sediment/sedimentary*, *sun/solar*, *moon/lunar*, *heat/thermal*,
   *digest/digestive*, *respiration/respiratory*, *circulation/circulatory*, *nerve/nervous*,
   *continent/continental*, *tide/tidal*, *metamorphosis/metamorphic*, and others. So in "layers of sediment pressed
   together … this rock is", the right answer *sedimentary* scored exactly 0. These are now separate concepts, and
   `facts_g2_links.txt` links them back to their base words.
2. **Stemmer collisions fixed.** *plane→plan* (a capped general word), *care→car*, *nuclear→nucleus*,
   *invisible→visible*, *insoluble→soluble*, *mate→mat*, *spine→spin*, *age→ag*, … (`same.txt`, last block).
3. **Direction concepts.** *more/increase/greater/high(er)* map to one concept and *less/fewer/decrease/reduce/low(er)*
   to another. The parent made *more* and *less* stop words and capped *increase* low. Direction words carry no
   topic, so they get no first-order associations and act only inside pairs: (*float*, *water*) recalls *less
   dense*, and (*altitude*, up) recalls *down pressure*. A pair that recalls one direction also argues against
   the other (×0.7). Topic clusters and "how high or low" definitions drop direction words.
4. **Negation without the "partner" term.** The parent's (NOT, q) rows also negated q's strongest pair recall.
   That flipped ordinary scenario questions ("the seeds did not sprout"): on my scenario-*not* questions it took
   accuracy from 90% down to 50%, and it didn't help true NOT questions. Now (NOT, q) negates only q's first-order
   answers, with `not` mild (0.4) and `except` strong (2.5).
5. **Category rules fire for members.** A rule whose cues name a taxonomy category (e.g. *herbivore*, *metal*,
   *color*) also fills the pair (member, other cue) at 0.5 with taxonomy decay. So a rule about *metal* + *heat*
   also answers a question about *copper* + *heat*.
6. **Definition chaining.** When a rule's answer is mainly a defined term (*camouflage*), the cues also recall the
   term's definition words (*blend in with surroundings*) at 0.5, because options often paraphrase the term.
7. **Multiword answers share weight.** Words of a multiword name (taxonomy entries, defined terms) recalled as an
   answer get 1/√k each, so *wheel and axle* and *carbon dioxide* don't win just by having two words.

## How it was checked

All checking was done by hand, on questions I invented (`/srv/work/qs/*.txt`, about 400 ARC-style questions,
copied into `/srv/work/my_questions.json`), using `scripts/explain.py` to read per-pair and per-concept
contributions. Each mechanism change was kept only when it was principled *and* not harmful on these questions.
No setting was searched. Accuracy on my sets is about 79%, against 78% for the parent. On my most ARC-like
"Challenge-style" sets it is about 70%. Real ARC is much harder than my own questions: the parent scored 47.7% on
validation while getting 55–90% on its writer's questions.

Known limits: no word order ("light is faster than sound" and "sound is faster than light" are the same bag); no
arithmetic; an option whose words all appear in the question scores 0; true NOT/EXCEPT questions are only partly
handled. A question that mentions both a property and its opposite (*renewable* and *nonrenewable*) is ambiguous.

## What generation 3 changed, and why

Each change comes from a fault seen in `scripts/explain.py` output (per pair and per concept contributions) on
invented questions. Each was kept only if it was principled and did not hurt the invented sets. No constant was
searched. The two constants that were compared against a few alternatives (A_UNIT, and the size of the pair
table) were set to the value the reasoning gave: A_UNIT equal to PAIR_UNIT, and the largest table that fits the
memory budget.

1. **First-order sums saturate (A_UNIT = 1).** The pair table already added recalls sublinearly, but `A` added
   them linearly. So a pair mentioned together in many lines (*atom* and *proton*) outweighed a specific rule
   (*negative charge* → *electron*). `A` now uses the same √ growth above 1.
2. **Bigger, sparser pair table (2^22 × 16 instead of 2^20 × 40).** A pair of question concepts that has no row
   of its own still reads whatever row it hashes to. At 2^20 about 12% of rows were occupied, so explanations kept
   showing recalls from unrelated pairs (e.g. *(not, person) → more*). At 2^22 about 3% are occupied. Only 8% of
   recall entries, the weakest ones of very long generic rows, fall beyond 16 per row. `build()` now frees the
   Python tables before allocating the tensors, so peak memory stays about 1.3 GB, as before. (A table with no
   collisions at all is impossible here: by Dirichlet's approximation theorem it needs more than C² ≈ 17M rows.)
3. **More pair-only concepts, like generation 2's more/less.**
   * *in* (absorb, inhale, intake) and *out* (release, emit, exhale, give **off**): "plants **give off**" and "plants
     **take in**" were the same bag. They are opposites, like more/less.
   * *without* (without, lack, no, none, absence): a rule whose cues contain it fills only the pairs that include it.
     So "animals **without** a backbone → invertebrate" no longer also fires for "animals **with** backbones".
   * *only*, *both*: "eats **only** plants" (herbivore) vs "eats **both** plants and animals" (omnivore).
   * *gain(s)* is now "more" and *lose(s)* "less". *greatest* was mapped to *great* rather than to "more"; fixed.
4. **Negation.** On 15 invented NOT/EXCEPT questions the parent was right once and ranked the right answer **last**
   14 times. A stronger negation helps those but flips scenario questions ("the seeds did not sprout"), as
   generation 2 found. Pair rows can't see whether *not* belongs to the question or to the scenario. So:
   * *except* (almost always a real negation) now also takes back what its concept recalls through a
     **phrase-mate**: a word that names one thing with it (taxonomy names, defined terms, e.g. *simple* +
     *machine*). In "all of these are simple machines EXCEPT", the (simple, machine) pair recall is what lifted
     the wrong options.
   * *not* cancels its concepts' first-order recall (strength 1.0, up from 0.4) but leaves pair recall alone. With
     the same knowledge this took negated questions from 1 to 3 of 15 and kept scenario-not at 10 of 12. The final
     model gets 4 of 15 and 9 of 12 (parent: 2 and 10).
   * *least* is treated like *not*: "which is least likely to conduct electricity" asks for the least supported
     option.
5. **Variable-identification questions.** For "which is the independent (dependent) variable", the answer names
   the factor the stem says was changed (measured). The architecture drops every option concept that the question
   has, so that option scored 0 and lost to any distractor bringing a weakly related word. When the question has
   *independent*, *dependent* or *manipulated*, each new option concept now costs a fixed amount. The usual result
   is a tie among options that only restate the stem, not a wrong pick.
6. **Morphology.** *collide/collision, expand/expansion, divide/division, compress/compression,
   survive/survival, die/death/dead, farm/farmer, hunt/hunter, strong/strength, deep/depth*, … are merged
   (`same.txt`, last block). *ramp* is no longer merged with *inclined*: in "which simple machine is a ramp?" that
   merge deleted *inclined* from the right answer.
7. **No negations on answer sides.** `not` and `cannot` are dropped from fact lines, so `physical change = … no new
   substance` taught that a physical change recalls *new substance*. Generation-3 lines avoid this
   (`nonliving`, `treeless`, `bare ground`, …).

## How generation 3 was checked

Using about 550 invented questions in `/srv/work/qs*/` (also in `/srv/work/my_questions.json`) with `/srv/work/scripts/`:
`ev.py` (accuracy, and gains and losses against the previous run) and `explain.py`:

| set | parent | generation 3 |
|---|---|---|
| all 551 | 77.6% | 87.1% |
| a fresh set written after most changes and never debugged (`qs4/h1.txt`, 50) | 88% | 90% |
| Challenge-style set, every distractor topically linked (`qs4/chal2.txt`, 25) | 61% | 89% (debugged afterwards) |
| NOT/EXCEPT (`qs3/neg.txt`, 15) / scenario-not (`qs3/scen_not.txt`, 12) | 2 / 10 | 4 / 9 |

These numbers say little about ARC. My questions are textbook-like, and on fresh ones both models score about
the same (88–90%), while the parent scored 48.9% on ARC validation. The gains above come mostly from questions
whose failures I read and then wrote knowledge for. I expect the ARC gain to come from the mechanism fixes (1–7),
which apply to every question, and from the breadth of the new rules and traps.

Known limits (in addition to those above): word order is invisible ("liquid to gas" = "gas to liquid", "north
and north" = "north"). Options that restate the question score 0. A topic word can still favor a wrong option
when no trap rule covers it. True NOT questions are still mostly wrong when the right answer is topically close
(*scar* among inherited traits).

## What generation 4 changed, and why

Each change below came from reading `scripts/explain.py` output (per pair and per concept contributions) on
questions I invented (`/srv/work/qs/*.txt`, 516 of them, also in `/srv/work/my_questions.json`). The ten example
questions in the task are in `qs/given.txt`, not in `my_questions.json`. No constant was searched.

1. **Negations inside fact lines (`parse_neg_line`).** The parent dropped *not/cannot/never/don't…* from fact lines.
   So `sound cannot travel > vacuum` taught (sound, travel) -> *vacuum*, and `sound needs > … not vacuum` did the
   same. About 400 lines had this problem. Now:
   * A negation on the **cue side** gates the rule. Only pairs that include a question negation concept (*#not* or
     the new *#cant*) recall the answer, and the rule gives no first-order or reverse recall (`NEG_GATES`, as
     generation 3's *#without*).
   * A negation on the **answer side** turns the next content word into evidence against (a `>!` answer).
   * `avoid` counts as a negation inside fact lines (`safe thunderstorm > go indoors avoid water`).
2. **New pair-only concept *#cant*** for *cannot, can't, don't, doesn't, didn't, won't, never*. The parent made them
   stop words. They are often scenario words ("animals cannot make their own food"), so they don't cancel
   anything. They only fire rules written with a negated cue.
3. **Tiered pair rows (`TIERS`, `P2`).** A pair row holds 16 recalls. The parent kept the 16 largest, and the
   chained definition words of a common answer (*solid* -> *definite shape volume tightly packed …*) filled the row
   of (sound, fast). That pushed the rule's own answers (*steel, iron*) out. Now a row first keeps the recalls
   that some directed rule (`>`, `=`, `>!`, taxonomy, negation) gives, then fills up with second-tier recalls
   (topic lines, `term = definition` word pairs, definition chaining).
4. **`not` negates like `except`** (`G_NOT = 2.5`, `P_NOT = 1.0`, previously 1.0 and 0.0). On 18 invented
   "which is NOT / EXCEPT" questions (`qs/neg.txt`), generation 3 was below chance (1 of 18; the parent 3 of 18).
   Cancelling only the first-order recall left the pair recall, so the most typical option still won. With the
   *except* strengths: 6 of 18. On 15 invented scenario-*not* questions (`qs/scen_not.txt`): 9 of 15 (10 of 15
   before). I expect true negations to be at least as common in ARC as scenario-*not* (state tests use "Which is
   NOT …" often), so this trade is worth it. One setting was compared, with the value taken from *except*, not
   tuned. A row can cancel only 16 recalls per (negation, concept) pair. An option that is related to the topic
   but outside those 16 keeps its positive score. This is the main remaining NOT failure (*lamp* in "not a
   source of light").
5. **Vocabulary and morphology.**
   * *take/takes/taken/took* -> *#in* ("plants **take in** carbon dioxide"). Cost: "how long does it take" now
     also has *#in*.
   * Digits 0-9 are concepts (water freezes at **0** °C).
   * *mostly* is a stop word. "made mostly of" recalled *hydrogen* through (earth, mostly).
   * *year/years/day/days* are no longer capped as general words, because they are often the answer.
   * Merged into one concept: *improve/improvement*, *dark/darkness*, *bright/brightness*, *thick/thickness*,
     *harm/harmful*, *help/helpful*, *lab/laboratory*, *barometer/barometric*, *hear/auditory*, and a few others
     (`same.txt`, last blocks).

Two other changes were tried and dropped. *avoid* as a question negation ("which activity should students avoid")
flipped "helps the earthworm avoid drying out". Ranking full rows by weight × idf instead of weight pushed
low-idf answers like *sun* and *water* out of rows.

### Knowledge added (`kb/facts_g4_*.txt`, about 2,500 lines)

| file | content |
|---|---|
| `facts_g4_phys.txt` | states and phase changes, properties, elements/compounds/mixtures, physical/chemical change, acids/bases, forces and motion, simple machines, energy forms and transformations, heat transfer, electricity, waves, sound, light |
| `facts_g4_earth.txt` | Earth's motions, seasons, Moon, Sun and stars, solar system, space exploration, Earth's layers, plates, earthquakes and volcanoes, rocks and minerals, weathering/erosion/soil, water and oceans, weather and climate, fossils and Earth history, resources and energy |
| `facts_g4_life.txt` | characteristics of life, cells, photosynthesis/respiration, plants, animal groups, adaptations and behavior, ecology, human impact, heredity, evolution, body systems, health, microorganisms |
| `facts_g4_inquiry.txt` | variables, fair tests, graphs, models, tools and units, lab safety, engineering design, technology and society |
| `facts_g4_cause.txt` | "what will most likely happen" cause → effect rules, and what speeds up or slows down a process |
| `facts_g4_items.txt`, `facts_g4_more.txt` | single test-item facts (senses, atom model, careers, everyday science, scientists) |
| `facts_g4_para.txt` | the most frequent facts in other wordings |
| `facts_g4_adv.txt` | middle-school detail for Challenge questions (periodic groups, solubility, pendulums, waves, Punnett ratios, brain parts, nitrogen fixing, crop rotation, …) |
| `facts_g4_why.txt` | "which best explains why" → the explanation's words |
| `facts_g4_traps.txt` | distractor traps (`weigh less moon >! less mass`, `renewable resource >! natural gas`) |

Some phrasings were chosen to avoid pair clashes. For example, `light travels fastest > vacuum` was reworded to
`light fastest speed > vacuum`, because its (fast, travel) pair also fired for "sound travels fastest through".

### How generation 4 was checked

`scripts/ev.py` (accuracy per file and gains/losses against a saved run) and `scripts/explain.py`, in
`/srv/work/scripts/`:

| set | generation 3 | generation 4 |
|---|---|---|
| all 526 (incl. the 10 task examples) | 79.7% | 85.0% |
| textbook-style sets debugged during the work (`earth`, `life`, `phys`, `chal`, 231) | 85.5% | 89.9% |
| fresh sets, scored when first written, before any debugging: `h1` (93) / `h3` (40) / `h5` (30) | 82.8 / 86.9 / 75.8 | 83.9 / 86.9 / 69.2 |
| the same fresh sets now (partly debugged afterwards) | same | 88.2 / 89.4 / 75.8 |
| `neg` (18) / `scen_not` (15) | 16.7 / 73.3 | 33.3 / 60.0 |

On questions it had never seen, generation 4 scored about the same as generation 3. Most of the gain is on
questions whose failures I read and then wrote knowledge for. Generation 3's own notes say the same about its
gains. On ARC I expect a small gain from the breadth of the new knowledge and from mechanisms 1, 3 and 4, which
apply to every question. Mechanism 4 matters most if ARC has as many true NOT questions as I think.

Known limits that remain: word order (orders of life cycles, "from producers to consumers" vs the reverse,
"light faster than sound" vs the reverse all tie). Direction words in options are not tied to their subject
("insects will increase" vs "fish will decrease" both read just the direction). Options that repeat question words
score 0 ("the seeds need water" when *water* is in the stem). Negation can cancel only 16 recalls per concept.

## What generation 5 changed, and why

The parent's question sets and scripts were not available, so I wrote new ones (`/srv/work/qs/*.txt`, 450
invented questions, also in `/srv/work/my_questions.json`) and new tools (`/srv/work/scripts/ev.py` for accuracy and
gains/losses against a saved run, `explain.py` for per-pair and per-concept contributions, `row.py` for one concept's
first-order row and pair rows). Every change below came from reading `explain.py` output. No constant was
searched. Where I compared settings, the value was fixed by reasoning first and two alternatives were only checked
for robustness.

### Mechanisms (`build.py`, all marked "generation 5")

1. **`take` is #in only in "take in / take up"** (`TAKE_DURATION`). Generation 4 mapped *take/takes* to #in, so
   duration lines ("earth rotation **takes** 24 hours") taught (#in, earth) -> *rotate, axis*. Then "Earth takes
   about 365 days to ..." picked *rotate*. In fact lines a *take* word not followed by *in/up* is now dropped.
   Questions are unchanged.
2. ***avoid* on the cue side is an ordinary word** (`NEG_CUE_KEEP`). Generation 4 treated *avoid* as a negation
   anywhere in a fact line, so no rule could answer "which activity should the students **avoid**". On the answer
   side it still negates the next word ("go indoors avoid water").
3. **Adjective opposites** (`ANTONYMS`, `ANT_OPP = 0.5`), the generation-2 more/less rule extended to about 35 pairs
   (*thick/thin, hot/cold, wet/dry, conductor/insulator, renewable/nonrenewable, physical/chemical, absorb/reflect*,
   ...). What a pair row or a first-order row recalls for one word counts against its opposite. In "polar bear ...
   cold climate", *thin fur* used to beat *thick layer of fat* on *fur*. Pairs that rules usually name together are
   left out (*day/night, east/west, push/pull, producer/consumer*), as is the ambiguous *light*.
4. **Pair-row fan-in damping** (`P_FAN_IN_REF = 1000`). *heat, water, sun, light, chemical, food, motion* are each
   recalled by 3,000 to 7,000 pair rows (median 20). Summed over a question's 120 pairs, such hubs outweighed a
   specific answer. The first-order table already damped hubs (`FAN_IN_REF`), but the pair table did not. Now each
   recall is scaled by 1/sqrt(1 + fan-in/1000), where 1000 is about the 99th percentile of fan-in, so only hubs
   change. Effect on all sets at the time: +5 / -2 questions. As a robustness check, 300 and 3000 were both
   slightly worse.
5. **Negation rows keep the concept's evidence against** (`NEG_KEEP_AGAINST = 4`). A (NOT, q) row keeps 16
   entries, and the strong positive recalls pushed out q's `>!` answers (*renewable >! coal*). Under NOT, those
   are exactly the answer. Only entries at least 30% of the row's largest are kept. Smaller ones were antonym
   spill-over noise. This had no measured effect on my 15 NOT questions, but it is principled and costs nothing.
6. **Stop words *as*, *once*.** *as* had idf 2.7 and was the strongest concept in "what happens ... **as** the
   ice melts".

One change was tried and dropped: **answer-side taxonomy**. A rule recalling a category would also recall its
members ("feathers" -> bird -> *robin*). It follows "mentions" rather than "is a": `compound = two or more
elements` made *compound* recall *gold* and *helium*. The result was -5 / +2.

### Knowledge (`kb/facts_g5_*.txt`, about 2,500 lines)

| file | content |
|---|---|
| `facts_g5_earth.txt`, `_life.txt`, `_body.txt`, `_phys.txt`, `_inquiry.txt` | the curriculum again in question wording (time periods of Earth's motions, moon, rocks, weather instruments, cells, ecology, body systems, forces, energy changes, waves, lab safety, tools, engineering, inventions, agriculture, everyday scenarios) |
| `facts_g5_reason.txt`, `_why.txt`, `_why2.txt` | evidence -> conclusion and phenomenon -> explanation ("same fossils on two continents > continents once joined", "pond freezes fish survive > ice floats insulates") |
| `facts_g5_impact.txt` | evaluative questions: harm / help the environment, positive / negative effect, advantages and disadvantages of energy sources and technologies, best material or tool for a purpose, everyday estimates, safe / unsafe, "purpose of ..." (the parent had 0 lines with "positive effect") |
| `facts_g5_tail.txt`, `_more.txt`, `_adv.txt` | long tail (landforms, maps, regions, ~100 organisms, careers and scientists, materials, everyday chemistry and physics) and middle-school depth (genetics ratios, reaction rates, periodic table, waves, Earth systems) |
| `facts_g5_traps.txt` | distractor traps. Single-cue traps were narrowed after review: `sun >! planet` would have argued against planets in every Sun question |

### How generation 5 was checked

Fresh sets were scored once, against the parent, before I read their failures:

| fresh set (first scoring) | parent | generation 5 at that time |
|---|---|---|
| `h1` (40, textbook style) | 80.8% | 80.8% (identical; +1 later from the antonym rule, which an h1 failure motivated) |
| `h2` (40) | 77.5% | 77.5% (identical per question) |
| `h3` (60) | 91.7% | 90.0% (one close loss, later fixed) |
| `m2` (30, ARC style: every option a topical multi-concept phrase) | 66.7% | 75.0% (+3, no losses) |
| `m3` (36, ARC style) | 77.8% | 77.8% (identical per question) |

After debugging, the final model scores 86.1% on all 450 questions, against 78.6% for the parent. No question
that the parent gets right is now wrong. Most of that gain is on questions whose failures I read and then wrote
knowledge for, as in earlier generations. On questions it had not yet seen, generation 5 was only slightly ahead of
the parent: +1.5 questions of 206 (+2.5 on `m2`, -1 on `h3`). I expect a small ARC gain, mostly on Easy questions that ask
for explanations, impacts and evaluations, and from mechanisms 1, 3 and 4, which apply to every question.

The `m` sets come closest to ARC's difficulty (both models 57-78% before debugging). Their failures are
mostly limits of the architecture:
* Direction words are not tied to their nouns. "ball rolls farther > **less** friction" makes (roll, farther)
  argue against "**raise** the height". An incidental "**high** shelf" in the stem drops #up from every option.
* Word-level concepts. *natural* in "natural gas" is the *natural* of "natural resource". *sunlight* is *sun*.
* "Which should be kept the same?": the right option usually restates the stem and scores 0.
* NOT rows hold 16 recalls. "Not found in a desert" cannot cancel *lizard* and *snake* when *desert* recalls more
  than 16 things. Negating a category every option shares (*resource*, *mammal*) adds noise.
* Longer options collect more partial matches ("reflection of light from Earth's cities").
