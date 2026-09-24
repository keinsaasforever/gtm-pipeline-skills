# Finder values — exact strings (read with cat, never paste into a SKILL.md)

A SKILL.md body cannot hold a dollar sign followed by a digit: the skill loader treats `$0`, `$1`, `$3`… as
argument placeholders and replaces them with words from the invocation. Every enum value that contains one
lives here. Values are case-sensitive; an off-list value silently matches nothing.

## BetterContact Lead Finder (checked against https://doc.bettercontact.rocks/api-reference/taxonomies, 2026-09-24)

### `revenue_ranges` (9)
`$0-$1M` `$1M-$5M` `$5M-$20M` `$20M-$100M` `$100M-$500M` `$500M-$1B` `$1B-$5B` `$5B-$10B` `$10B+`

### `lead_seniority` (12)
`c_suite` `vp` `director` `head` `manager` `senior` `mid-level` `entry` `founder` `owner` `partner` `intern`

### `company_industry` (120 Landbase values)
⚠ **Zero the whole query** (measured, each returns 0 alone and zeroes any list it joins): Architecture & Planning,
Broadcast Media, Gambling & Casinos, Internet, Marketing & Advertising, Mechanical or Industrial Engineering,
Sports, Staffing & Recruiting, Wireless. There is **no Machinery value**. `company_hq_location` is not honoured
(Germany returned South African and flight-school rows): enforce HQ locally, or scope by a `company` domain list.

Accounting · Airlines/Aviation · Alternative Medicine · Animation · Apparel & Fashion · Architecture & Planning ·
Automotive · Aviation & Aerospace · Banking · Biotechnology · Broadcast Media · Building Materials · Business
Supplies & Equipment · Capital Markets · Chemicals · Civic & Social Organization · Civil Engineering · Commercial
Real Estate · Computer & Network Security · Computer Games · Computer Hardware · Computer Networking · Computer
Software · Construction · Consumer Electronics · Consumer Goods · Consumer Services · Cosmetics · Defense & Space ·
Design · E-Learning · Education Management · Electrical & Electronic Manufacturing · Entertainment · Environmental
Services · Events Services · Executive Office · Facilities Services · Financial Services · Fine Art · Food &
Beverages · Food Production · Gambling & Casinos · Government Administration · Government Relations · Graphic
Design · Health, Wellness & Fitness · Higher Education · Hospital & Health Care · Hospitality · Human Resources ·
Individual & Family Services · Industrial Automation · Information Services · Information Technology & Services ·
Insurance · International Affairs · International Trade & Development · Internet · Investment Banking · Investment
Management · Law Enforcement · Law Practice · Legal Services · Leisure, Travel & Tourism · Logistics & Supply Chain ·
Luxury Goods & Jewelry · Management Consulting · Maritime · Market Research · Marketing & Advertising · Mechanical
or Industrial Engineering · Media Production · Medical Device · Medical Practice · Mental Health Care · Military ·
Mining & Metals · Motion Pictures & Film · Music · Nanotechnology · Non-profit Organization Management · Oil &
Energy · Online Media · Outsourcing/Offshoring · Package/Freight Delivery · Performing Arts · Pharmaceuticals ·
Philanthropy · Photography · Political Organization · Primary/Secondary Education · Professional Training &
Coaching · Program Development · Public Policy · Public Relations & Communications · Publishing · Real Estate ·
Religious Institutions · Renewables & Environment · Research · Restaurants · Retail · Security & Investigations ·
Semiconductors · Shipbuilding · Software Development · Sports · Staffing & Recruiting · Telecommunications · Think
Tanks · Translation & Localization · Transportation/Trucking/Railroad · Utilities · Venture Capital & Private
Equity · Veterinary · Wholesale · Wine & Spirits · Wireless · Writing & Editing

## Pipe0 `crustdata@3` — `current_employer_estimated_revenue` (5)
`$0-$1M` `$1M-$10M` `$10M-$100M` `$100M-$1B` `$1B+`

## FullEnrich
LinkedIn industries: `_shared/fe_industries.txt` (490, case-insensitive). FE has what BetterContact lacks, e.g.
`Machinery Manufacturing`, `Industrial Machinery Manufacturing`, `Aviation and Aerospace Component Manufacturing`,
`Defense and Space Manufacturing`.
