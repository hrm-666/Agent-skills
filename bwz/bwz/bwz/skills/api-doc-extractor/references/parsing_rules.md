# Parsing Rules

## Main request construction path

For GET endpoints, build the final request URL from:

1. The method row endpoint URL.
2. Query values found in the request parameter table or nearby same-block text.
3. Values explicitly provided by the user.

Example URLs are fallback and validation sources only. Real project documents may not include examples.

## Interface block shape

An API document block may contain:

- A title.
- A method and endpoint row.
- A request parameter table.
- Optional request examples.
- A response field table.

## Parameter table rules

- GET tables may be `name | required | description`.
- POST tables may be `name | type | required | description`.
- Indentation indicates nested Object or Array fields.
- Placeholder descriptions such as `contact us` or `联系我们获取` are not values.
- Defaults like `page = 1` are metadata and should only be used when needed.

## Response field rules

- Use indentation to build paths.
- Object children use `parent.child`.
- Array children use `parent[].child`.
- Preserve duplicate leaf names by including their parents, such as `reward.id` and `addons[].id`.
