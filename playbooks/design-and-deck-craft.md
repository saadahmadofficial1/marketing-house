# Design and deck craft

My standing rules for any presentation: the titles carry the story, slides stay light, type is big enough to read from the back of the room, and nothing looks like a generic AI-generated deck. It is short on purpose – these are the rules I check every deck against, not a design course.

- **The wider look:** [Style DNA](style-dna.md) – colours, type, captions and backgrounds across all my work
- **Tools:** [`sa_font.py`](../tools/sa_font.py) installs a chosen typeface as real font files with a load test · [`sa_qa.py`](../tools/sa_qa.py) checks British spelling before anything goes out · [`sa_titlecard.py`](../tools/sa_titlecard.py) applies the same two-tier title hierarchy to video title cards
- **Public source for the “AI look” section:** Anthropic’s [frontend aesthetics prompting guide](https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb) in the claude-cookbooks repository

| Part | Status |
|---|---|
| The rules on this page | **Built, in use** – my standing rules for every deck |

---

## 1. The titles carry the story

Read the slide titles alone, top to bottom. They should track like the chapter list of a book: someone who reads nothing else should still get the argument.

**Pick one title style and hold it on every slide** – either short topic noun phrases or brief declarative sentences, never a mix.

A constructed example of the same five-slide section:

| Mixed and leaky | One style, tracks as a story |
|---|---|
| Overview | Where the time goes today |
| The magic moment | Three steps cause most of the delay |
| It’s not a tool problem, it’s a process problem | The delay is in hand-offs, not software |
| Numbers!! | Hand-offs take 40% of each request |
| What if…? | Two changes remove most hand-offs |

---

## 2. Titles introduce; they don’t perform

- **No punchline titles** – “It’s not X, it’s Y”, “The magic moment”.
- **No faux suspense or heavy reframing.** A title introduces the slide plainly; it is not the speaker’s zinger. The punchline, if there is one, belongs to the person presenting.

---

## 3. Don’t overload a slide

- When a slide is crowded, change its form instead of shrinking the text: **a table, a big number, a quote, a diagram or an image.**
- Less is more. No filler sections and no stat-slop – a number is on a slide because it matters, not because it is available.
- **Ask before adding material** that wasn’t in the brief.

---

## 4. Size for the room (1920 × 1080)

| Element | Minimum |
|---|---|
| Body text | **24 px** |
| Titles | **48 px** |

When a brief gives sizes in points, convert: **px = pt × 1.333**.

| Points | Pixels |
|---:|---:|
| 18 pt | 24 px |
| 24 pt | 32 px |
| 36 pt | 48 px |

So “36 pt titles” already meets the 48 px floor, and “14 pt body” (about 19 px) does not.

---

## 5. Parallelism

- **Section-header slides look identical** to each other, apart from their words.
- **Repeated elements sit in the same position** on every slide – page numbers, logos, source lines, the title block. Movement between slides should come from the content, not from things that should have stayed still.

---

## 6. Restraint in type and colour

- **One or two typefaces** at most.
- **One or two background colours** at most.
- Use the brand’s own typefaces and colours, and derive any extra tints from them rather than inventing new colours ([Style DNA, section 3](style-dna.md#3-background-style-by-mode-and-occasion)).

---

## 7. Don’t borrow someone else’s look

Don’t recreate another company’s distinctive or branded interface on a slide. A layout that is recognisably someone else’s product reads as theirs, whatever the words say.

---

## 8. Avoiding the generic “AI look”

Only points that a public source states. Anthropic’s frontend aesthetics prompting guide names these as the tells of generic AI-generated design and the habits that avoid them:

- **Overused font families** – Inter, Roboto, Arial and system fonts. Choose a distinctive face deliberately instead.
- **Clichéd colour schemes**, particularly purple gradients on white backgrounds.
- **Predictable layouts and component patterns**, and cookie-cutter design without context-specific character.
- **Commit to one cohesive look.** A dominant colour with sharp accents beats a timid palette spread evenly across everything.

The guide is written for web front ends; each of these points applies to slides as well.

---

## Related

- [Style DNA](style-dna.md) – the look on one page: guardrails, colour, type, captions, formats
- [Occasions calendar and visual guide](designing-for-gulf-occasions.md) – design modes and palettes by occasion
- [My creative bar](my-creative-bar.md) – complete not condensed, the two-tier text hierarchy, and status honesty in anything I present
- [Thinking prompts](thinking-prompts.md) – the critique and blind-spot prompts I run on a draft deck
