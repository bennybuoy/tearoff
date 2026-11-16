# Edition file reference

Both layouts read one JSON file. Start from an example in `examples/`; this page
explains what each key does and how long the text can be. "Max" lengths are
characters, counted roughly. When in doubt, shorter.

Times are 24-hour strings like `"08:35"`. `date` is `"YYYY-MM-DD"`.

## Newspaper (`scripts/briefing.py`)

| Key | Required | What it is |
|---|---|---|
| `date` | yes | The day. Sets the masthead weekday and the moon. |
| `issue` | yes | Edition number. |
| `week` | no | Top right of the masthead, e.g. `"WK 6"`. Max 8. |
| `masthead` | no | Defaults to the `masthead` in your config (`THE DAILY BRIEFING`). |
| `headline` | yes | List of 1 to 3 lines. Type shrinks to fit the longest line, so keep lines under 16 so it stays big. |
| `deck` | yes | One or two sentences under the headline. Max 120. |
| `weather` | yes | Paste the `weather` block from `facts.py`, then add the three keys below. |
| `weather.notes` | yes | List of 1 or 2 sentences about what the weather means for this day. Max 130 each. |
| `weather.bands` | no | Bars under the chart: `[start_hour, end_hour, "LABEL", solid]`. Hours are decimals (8:35 is `8.58`). `solid` is `true` for a black bar. Label max 12, and the bar must be wide enough to hold it (about 1 hour per 4 letters). |
| `weather.mark_hours` | no | Extra hours (whole numbers, 6 to 22) to label with a temperature dot. The max, 7 am and 10 pm are always labelled. |
| `day` | yes | The timeline. List of `[start, end, kind, title, detail]`. See below. |
| `day_span` | yes | `[first, last]` time shown on the timeline. Use about 20 min before the first item and 15 min after the last. |
| `day_notes` | no | List of short notes under the timeline. Max 130 each. |
| `gap` | with ticket | Italic line between the timeline and the ticket, e.g. `"1 h 45 min from last bell to gates"`. Max 40. |
| `ticket` | no | The ticket stub. Delete the key on days with no event. See below. |
| `todo` | yes | List of `[GROUP LABEL, [items…]]`. Group label max 18, capitals. Items max 110. |
| `blank_todos` | no | Empty write-in lines after the to-dos. Default 3. |
| `tomorrow` | no | `title` (weekday in capitals), `rows` as `[time, what, where]`, `note`. `what` max 14, `where` max 22. |
| `numbers` | yes | Exactly 3 pairs `[big, small label]`. Use the ones from `facts.py`. |
| `fact_head` | yes | Usually `"ONE TRUE THING"`. |
| `fact` | yes | The fun fact. Max 190. |
| `signoff` | yes | Last line, e.g. `"Have a great one, Sam."` Max 26. |

### `day` rows

`kind` is one of:

- `class`: solid black block. `title` is the class code (max 8), `detail` is
  `"Year 9 Maths  ·  M2"` (max 30).
- `meet`: outlined block. `title` max 26, `detail` unused (`""`).
- `duty`: striped block. `title` like `"DUTY  Oval"` (max 26).
- `free`: dotted block. `title` max 20, `detail` like `"60 min"`.

Blocks are drawn to scale. Anything shorter than 20 minutes is too thin to read:
leave it out and mention it in `day_notes`. Do not overlap blocks. You do not need
to fill every gap; leave real gaps empty or cover them with a `free` block if the
free time is worth pointing out.

### `ticket`

| Key | What it is |
|---|---|
| `kicker` | Black band text, e.g. `"TONIGHT  ·  THU 12 MAR"`. Max 26. |
| `act` | Big name. Each word goes on its own line. 1 to 3 words. |
| `tour` | Small caps line. Max 24. |
| `venue` | Max 36. |
| `cells` | Exactly 4 pairs `[LABEL, value]`, e.g. `["DOORS","6:00"]`. Labels max 6, values max 6. |
| `foot` | Small line under the ticket. Max 56. |
| `stub` | Sideways text on the stub, e.g. `"ADMIT FOUR"`. Max 12. |

## Gig poster (`scripts/briefing_gig.py`)

| Key | Required | What it is |
|---|---|---|
| `date` | yes | The day. Used for the moon icon. |
| `issue` | yes | Edition number. |
| `top` | yes | Strip above the title, e.g. `"ONE DAY ONLY"`. Max 18. |
| `title` | yes | The weekday in capitals. |
| `tour` | yes | White banner under the title. A joke name for the day. Max 26. |
| `strip` | yes | Bottom of the header: date and places. Max 46. |
| `lineup_kicker` | yes | Small line above the bill. Max 34. |
| `headliner` | yes | List of 1 or 2 words, each its own huge line. The main thing of the day. |
| `second` | yes | Second line of the bill, e.g. `"9MA  +  10MA"`. Max 20. |
| `third` | no | List of up to 2 small lines. Max 40 each. |
| `fourth` | no | One italic line. Max 34. |
| `stages` | yes | List of `[BAR LABEL, [rows…]]`. Each row is `[time, what, where, note]`. |
| `sky` | no | Weather row: 4 to 6 entries `[when, kind, temp, tag]`. |
| `sky_note` | no | Sentence under the weather row. Max 170. |
| `entry` | no | Rules box: list of `[allowed, headline, detail]`. Event days only. |
| `entry_title`, `entry_src` | no | Box title and the small source line. |
| `rider` | no | To-dos, same shape as newspaper `todo`. |
| `blank` | no | Empty write-in lines. Default 3. |
| `inbox` | no | List of `[LABEL, text]`. Label max 12 capitals, text max 120. Up to 6. |
| `encore` | no | Next school day: rows `[time, what, where]`. |
| `encore_title` | no | e.g. `"ENCORE  ·  THURSDAY"`. |
| `sides` | yes in practice | The fun facts: list of `[SIDE A, text]`. One or two. Text max 220. |
| `card` | no | Tear-off pocket card. Event days only. See below. |
| `sign` | no | Last line, e.g. `"NO. 040  ·  PRINTED FOR WED 11 MAR"`. |

### `stages` rows

- `time`: `"08:35"`. Use `"__:__"` to draw an empty box for the user to write a time in.
- `what`: bold title, max 18.
- `where`: right-aligned, max 20. `what` and `where` share one line, so together
  stay under 34.
- `note`: optional sentence underneath, max 130. Use `""` for none.

Bar labels look like `"STAGE ONE  ·  SCHOOL"` (max 30). One stage is fine.

### `sky` entries

Build them from `sky_at` in the `facts.py` output: pick the hours that matter to
the day, copy `kind` and `temp`. `when` is a short label (`"8 am"`, `"7:45"`).
`kind` must be `sun`, `cloud`, `rain` or `moon`. `tag` is an optional word in a
black chip (max 6), e.g. `"61%"`, `"show"`.

### `entry` rows

`[false, "No backpacks.", "Bag must be under A4."]` draws a crossed circle.
`[true, "Tickets in your phone wallet", "before you leave."]` draws a tick.
Headline max 38, detail max 40.

### `card`

| Key | What it is |
|---|---|
| `times` | Exactly 3 pairs `[LABEL, value]`. Values max 5. |
| `seats` | One line, max 36. |
| `home_k`, `home`, `home_d` | Label, big value (max 9) and small detail (max 44) for the white box: the one thing the user must not miss, usually the way home. |
| `rules` | Small caps line, max 44. |

Print gig editions that have a `card` with `--split` so the card is cut off as its
own piece.
