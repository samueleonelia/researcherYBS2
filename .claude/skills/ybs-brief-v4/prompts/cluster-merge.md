# Merge the parts into one plan

Today's kept list was too long for one call, so it was cut into {{PARTS}} parts
and each part was grouped into news items on its own. You see every item every
part made, with the articles inside it. One job: produce the single plan the run
would have had if one agent had seen the whole list.

Nothing is opened here. The lines the parts saw are all the evidence there is.

## Inputs

- Date: `{{DATE}}` · slot: `{{SLOT}}`
- The items, part by part. An item's first line gives its part and id, its kind,
  its verdict, its profile, its primary, its read list and the reason its part
  gave; its article lines follow, as the part saw them:

```
{{PART_ITEMS}}
```

## What he is arguing about now

Rebuilt from his latest shows on {{PROFILE_DATE}}. A merged item is judged
against this list again, and its `profile` is copied from here character for
character.

{{PROFILE}}

## What the show covers at all

{{BEATS}}

## What the brief is for

{{LENS}}

## The job

- Items from **different** parts that report the same event become one item.
  Union their articles; choose the primary and the `read` list again, asking of
  each other article whether it promises a fact or an angle the primary's
  description does not carry; judge `verdict` and `profile` again for the
  merged item.
- Items from the **same** part are never merged. That part already judged them
  side by side.
- Every other item passes through unchanged: same articles, same primary, same
  `read`, same verdict, same profile, same `why`.
- Give every item a fresh id, `i01` onwards. The parts' ids are not yours.
- Order the whole list so the most consequential item comes first. A part could
  only order what it saw; your order is the tie-break code uses.
- Carry every near miss the parts reported into `near_misses`, then add the
  pairs you nearly merged across parts.

## Output

One JSON object and nothing else, in the shape a part used. Here two parts had
each found the same fine, and one part's column passes through:

```json
{
  "items": [
    {
      "item_id": "i01",
      "name": "Dutch regulator fines Uber $966m",
      "kind": "cluster",
      "verdict": "READ",
      "profile": "Capitalism versus the mixed economy",
      "articles": ["a033", "a210"],
      "primary": "a033",
      "read": ["a033"],
      "why": "merged 1/i02 and 2/i05, the same fine; a210 promises nothing a033 lacks"
    },
    {
      "item_id": "i02",
      "name": "Column: the guardrails AI needs",
      "kind": "single",
      "verdict": "MAYBE",
      "profile": "Technology and AI as human progress",
      "articles": ["a058"],
      "primary": "a058",
      "read": ["a058"],
      "why": "passed through from 1/i03"
    }
  ],
  "near_misses": [
    "part 1: a012 and a091: both about the Pentagon, but a firing and a budget request are different events",
    "1/i04 and 2/i01: both on the strike, but the walkout and its court ruling are different events"
  ]
}
```

{{ITEM_SHAPE}}

## Hard rules

1. Every article id the parts hold appears in exactly one item of yours. Code
   checks the merged plan against the whole kept list.
2. Never merge two items from the same part.
3. How many items get read is not yours to decide, and neither is what leads.
   Code applies the ceilings; the pick comes later, once the stories are read.
