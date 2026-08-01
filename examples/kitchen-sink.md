---
title: Front matter is stripped, just like on GitHub
---

# Kitchen Sink :tada:

A single document exercising every construct the renderer supports, so the
output can be compared side by side with GitHub.

## Inline formatting

**Bold**, *italic*, ***both***, ~~struck through~~, `inline code`, <kbd>Ctrl</kbd> +
<kbd>C</kbd>, H<sub>2</sub>O, x<sup>2</sup>, and an intraword_underscore_name that
must *not* become italic.

Escapes: \*not emphasis\*, \_not italic\_, and a literal backslash \\.
Entities: &amp; &copy; &#169; &hearts;. A code span with backticks: `` ` ``.

Hard break with two spaces:  
this line follows a `<br>`.

## Links and images

[Inline link](https://example.com "With a title"), [reference link][ref],
[collapsed][], and a [shortcut]. Bare URL: https://example.com/path?q=1 and
www.example.com and an email a@b.example.com.

[ref]: https://example.com/reference
[collapsed]: https://example.com/collapsed
[shortcut]: https://example.com/shortcut

## Lists

- Unordered item
- Another, with a nested list:
  - Nested one
    - Nested two
- Item with a paragraph

  Second paragraph inside the same item.

1. Ordered
2. Items
7. Numbers after the first are ignored

- [x] Completed task
- [ ] Outstanding task
  - [x] Nested completed task

Term
: Definition-style content is not GFM, so this stays a paragraph.

## Blockquotes and alerts

> A plain blockquote.
>
> > Nested one level deeper.

> [!NOTE]
> Useful information a reader should notice even when skimming.

> [!TIP]
> Optional advice for doing something better.

> [!IMPORTANT]
> Key information the reader needs to achieve their goal.

> [!WARNING]
> Urgent content requiring immediate attention.

> [!CAUTION]
> Advises about risks or negative outcomes.

## Tables

| Language | Typing | Released | Notes |
|:---------|:------:|---------:|-------|
| Python   | dynamic | 1991 | Uses `\|` escaped in a cell |
| Rust     | static  | 2015 | **Bold** and [a link](https://example.com) |
| Go       | static  | 2009 | ~~struck~~ |

## Code

Indented code block:

    def indented():
        return "never highlighted"

Python:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Point:
    """A point in two dimensions."""
    x: float = 0.0
    y: float = 0.0

    def distance_to(self, other: "Point") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

if __name__ == "__main__":
    print(f"{Point(3, 4).distance_to(Point()):.2f}")  # 5.00
```

JavaScript:

```javascript
const cache = new Map();

export async function fetchUser(id, { signal } = {}) {
  if (cache.has(id)) return cache.get(id);
  const response = await fetch(`/api/users/${id}`, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const user = await response.json();
  cache.set(id, user);
  return user;
}
```

HTML:

```html
<!DOCTYPE html>
<html lang="en">
  <head><meta charset="utf-8"><title>Demo</title></head>
  <body><p class="intro">Hello &amp; welcome</p></body>
</html>
```

Shell:

```bash
#!/usr/bin/env bash
set -euo pipefail
for file in "$@"; do
  [[ -f "$file" ]] || { echo "missing: $file" >&2; continue; }
  wc -l < "$file"
done
```

Diff:

```diff
--- a/config.yaml
+++ b/config.yaml
@@ -1,4 +1,4 @@
 name: service
-replicas: 1
+replicas: 3
 image: app:latest
```

SQL and JSON:

```sql
SELECT u.name, COUNT(o.id) AS orders
FROM users AS u LEFT JOIN orders AS o ON o.user_id = u.id
WHERE u.created_at >= '2024-01-01' GROUP BY u.name HAVING COUNT(o.id) > 5;
```

```json
{ "name": "demo", "version": "1.0.0", "private": true, "nested": [1, 2.5, null, false] }
```

An unknown language falls back to plain text:

```notalanguage
this is *not* highlighted
```

## Raw HTML

<details>
<summary>Click to expand</summary>

Markdown **inside** an HTML block still renders.

</details>

<script>alert("this is removed by the sanitiser")</script>

## Footnotes

Statements can cite sources[^source], including named ones[^named].

[^source]: The first footnote.
[^named]: A footnote with a text label.

## Headings repeat

### Repeated heading
### Repeated heading
### Repeated heading

## Unicode

Grüße aus Brandenburg · 日本語の見出し · Ελληνικά · Привет мир · 🎉 🚀 ✅

---

That horizontal rule ends the document.
